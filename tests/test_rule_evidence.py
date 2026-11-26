import uuid
from sqlalchemy import select, delete, func
from backend.database import (SessionLocal, ConditionRuleMatch, ConditionRuleDeployment, ConditionRuleReview,
                              Reading, User, SiteMembership, LoginSession, Audit, WorkOrder)
from backend.security import password_hash
from test_live_rules import cleanup_live_fixture, call, ingest
from test_rule_reviews import match_fixture


def test_evidence_uses_exact_trigger_reading_and_matched_revision_without_writes(client, sign_in):
    asset, rule, match_id = match_fixture(client, sign_in)
    with SessionLocal() as db:
        match = db.get(ConditionRuleMatch, match_id)
        reading_id, timestamp = match.trigger_reading_id, match.triggered_at
    changed = call(client, f"/api/condition-rules/drafts/{rule['id']}", dict(**rule['settings'],
                   name="Later draft", reason="Later draft must not replace historical evidence", expected_version=1) | {"threshold": 99})
    assert changed.status_code == 200, changed.text
    assert ingest(client, asset, timestamp + 10, 1).status_code == 200
    with SessionLocal() as db:
        before = {model.__tablename__: db.scalar(select(func.count()).select_from(model))
                  for model in (Audit, WorkOrder, ConditionRuleReview, Reading)}
    sign_in("engineer")
    result = client.get(f"/api/condition-rules/matches/{match_id}/evidence")
    assert result.status_code == 200, result.text
    data = result.json()
    assert data['asset']['tag'] == asset['tag']
    assert data['rule']['version'] == 1 and data['rule']['settings']['threshold'] == 5
    assert data['snapshot']['id'] == reading_id and data['snapshot']['timestamp'] == timestamp
    assert data['snapshot']['quality'] == 'good'
    assert data['snapshot']['signals'][0] == {'channel': 'vibration', 'unit': 'mm/s', 'value': 7}
    assert data['match']['signal_state'] == 'paused'
    assert 'full persistence sequence' in data['boundary']
    with SessionLocal() as db:
        assert before == {model.__tablename__: db.scalar(select(func.count()).select_from(model))
                          for model in (Audit, WorkOrder, ConditionRuleReview, Reading)}
        assert db.get(ConditionRuleMatch, match_id).state == 'paused'
        assert db.get(ConditionRuleDeployment, rule['id']).state == 'paused'


def test_evidence_role_site_missing_match_and_authentication(client, sign_in):
    asset, rule, match_id = match_fixture(client, sign_in)
    path = f"/api/condition-rules/matches/{match_id}/evidence"
    sign_in('planner')
    assert client.get(path).status_code == 403
    with SessionLocal() as db:
        email = uuid.uuid4().hex + '@example.invalid'
        user = User(name='Scoped evidence engineer', email=email, role='engineer', sites=['Habshan Processing Hub'],
                    password_hash=password_hash('Evidence fixture password 2026!'))
        db.add(user); db.flush(); user_id = user.id; db.commit()
    try:
        login = client.post('/api/auth/login', json={'email': email, 'password': 'Evidence fixture password 2026!'})
        assert login.status_code == 200
        assert client.get(path).status_code == 404  # Existing site guard conceals out-of-scope equipment.
        sign_in('admin')
        assert client.get('/api/condition-rules/matches/missing/evidence').status_code == 404
        client.cookies.clear()
        assert client.get(path).status_code == 401
    finally:
        with SessionLocal() as db:
            db.execute(delete(LoginSession).where(LoginSession.user_id == user_id))
            db.execute(delete(SiteMembership).where(SiteMembership.user_id == user_id))
            db.execute(delete(User).where(User.id == user_id)); db.commit()


def test_evidence_rejects_cross_equipment_link_without_disclosing_snapshot(client, sign_in):
    asset, rule, match_id = match_fixture(client, sign_in)
    with SessionLocal() as db:
        other = db.scalar(select(Reading).where(Reading.asset_id != asset['id']))
        assert other
        match = db.get(ConditionRuleMatch, match_id)
        original = match.trigger_reading_id
        match.trigger_reading_id = other.id; db.commit()
    try:
        result = client.get(f"/api/condition-rules/matches/{match_id}/evidence")
        assert result.status_code == 409 and 'snapshot' not in result.json()
    finally:
        with SessionLocal() as db:
            db.get(ConditionRuleMatch, match_id).trigger_reading_id = original; db.commit()


def test_evidence_handles_nonfinite_legacy_context_value(client, sign_in):
    asset, rule, match_id = match_fixture(client, sign_in)
    with SessionLocal() as db:
        match = db.get(ConditionRuleMatch, match_id)
        db.get(Reading, match.trigger_reading_id).temperature = float('inf'); db.commit()
    result = client.get(f"/api/condition-rules/matches/{match_id}/evidence")
    assert result.status_code == 200, result.text
    temperature = next(s for s in result.json()['snapshot']['signals'] if s['channel'] == 'temperature')
    assert temperature['value'] is None
