import uuid
import pytest
from sqlalchemy import select, func, delete
from backend.database import (SessionLocal, ConditionRuleMatch, ConditionMatchInvestigation, ConditionRuleDeployment,
                              ConditionRuleReview, ConditionRuleAssignment, Investigation, RecommendationRevision,
                              WorkOrder, Audit, Reading, User, SiteMembership, LoginSession, Asset, now)
from backend.security import password_hash
from backend.seed import payload_hash
from test_live_rules import cleanup_live_fixture, call, ingest
from test_rule_reviews import match_fixture


def prepare(client, match_id, key=None, reason='Synthetic investigation acceptance; no physical maintenance.', title=''):
    return call(client, f'/api/condition-rules/matches/{match_id}/investigation', dict(title=title, reason=reason), key)


def test_match_investigation_pins_evidence_duplicate_protection_and_preserves_review_state(client, sign_in):
    asset, rule, match_id = match_fixture(client, sign_in)
    with SessionLocal() as db:
        match = db.get(ConditionRuleMatch, match_id)
        trigger_id, timestamp = match.trigger_reading_id, match.triggered_at
        orders = db.scalar(select(func.count()).select_from(WorkOrder))
    assert ingest(client, asset, timestamp + 10, 2).status_code == 200
    changed = call(client, f"/api/condition-rules/drafts/{rule['id']}", dict(**rule['settings'], name='Newer draft', reason='Later revision fixture', expected_version=1) | {'threshold': 99})
    assert changed.status_code == 200
    path = f'/api/condition-rules/matches/{match_id}/investigation'
    assert client.get(path).json()['ready'] is True
    key = str(uuid.uuid4())
    result = prepare(client, match_id, key)
    assert result.status_code == 201, result.text
    first = result.json()
    assert first['created'] is True
    inv = first['investigation']; origin = inv['payload']['condition_origin']
    assert inv['state'] == 'awaiting_review' and inv['approver'] is None
    assert inv['payload']['requires_approval'] and inv['payload_hash'] == payload_hash(inv['payload'])
    assert origin['rule']['version'] == 1 and origin['rule']['settings']['threshold'] == 5
    assert origin['snapshot']['id'] == trigger_id and origin['snapshot']['signals'][0]['value'] == 7
    assert origin['analysis_snapshot']['id'] != trigger_id and origin['analysis_snapshot']['signals'][0]['value'] == 2
    assert prepare(client, match_id, key).json() == first
    duplicate = prepare(client, match_id, title='Different title must not create another record').json()
    assert duplicate['created'] is False and duplicate['investigation']['id'] == inv['id']
    assert prepare(client, match_id, key, reason='Different content with the same key').status_code == 409
    assert client.get(path).json()['investigation']['id'] == inv['id']
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ConditionMatchInvestigation).where(ConditionMatchInvestigation.match_id == match_id)) == 1
        revisions = list(db.scalars(select(RecommendationRevision).where(RecommendationRevision.investigation_id == inv['id'])))
        assert len(revisions) == 1 and revisions[0].payload['condition_origin'] == origin
        assert db.get(ConditionRuleMatch, match_id).state == 'paused'
        assert db.get(ConditionRuleDeployment, rule['id']).state == 'paused'
        for model in (ConditionRuleReview, ConditionRuleAssignment):
            assert db.scalar(select(func.count()).select_from(model).where(model.match_id == match_id)) == 0
        assert db.scalar(select(func.count()).select_from(WorkOrder)) == orders
        assert db.scalar(select(func.count()).select_from(Audit).where(Audit.action == 'Condition investigation prepared', Audit.target == asset['tag'])) == 1


@pytest.mark.parametrize('invalid', ['stale', 'bad_quality', 'future', 'nonfinite'])
def test_match_investigation_rejects_unusable_current_snapshot_without_partial_writes(client, sign_in, invalid):
    asset, rule, match_id = match_fixture(client, sign_in)
    with SessionLocal() as db:
        row = db.get(Reading, db.get(ConditionRuleMatch, match_id).trigger_reading_id)
        if invalid == 'stale': row.timestamp = now() - 7200
        if invalid == 'bad_quality': row.quality = 'bad'
        if invalid == 'future': row.timestamp = now() + 600
        if invalid == 'nonfinite': row.flow = float('inf')
        before = db.scalar(select(func.count()).select_from(Investigation)); db.commit()
    assert client.get(f'/api/condition-rules/matches/{match_id}/investigation').json()['ready'] is False
    assert prepare(client, match_id).status_code == 409
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Investigation)) == before
        assert db.get(ConditionMatchInvestigation, match_id) is None


def test_match_investigation_keeps_independent_approval_and_captured_origin_on_edits(client, sign_in):
    asset, rule, match_id = match_fixture(client, sign_in)
    result = prepare(client, match_id).json()['investigation']
    inv_id = result['id']; origin = result['payload']['condition_origin']
    decision = dict(expected_version=1, decision='approve', reason='Reviewed synthetic evidence only.')
    assert call(client, f'/api/investigations/{inv_id}/decision', decision).status_code == 403
    assert call(client, '/api/work-orders', dict(investigation_id=inv_id, expected_version=1, due_date='2026-12-01')).status_code == 409
    sign_in('approver')
    approved = call(client, f'/api/investigations/{inv_id}/decision', decision)
    assert approved.status_code == 200, approved.text
    sign_in('engineer')
    edited = client.patch(f'/api/investigations/{inv_id}', json={'expected_version': approved.json()['version'],
                          'recommendation': 'Review current synthetic readings and verify procedure applicability.',
                          'checklist': ['Verify sensor mounting and operating context.']}, headers={'Idempotency-Key': str(uuid.uuid4())})
    assert edited.status_code == 200, edited.text
    assert edited.json()['state'] == 'awaiting_review' and edited.json()['approver'] is None
    assert edited.json()['payload']['condition_origin'] == origin
    assert edited.json()['payload_hash'] != approved.json()['payload_hash']
    history = client.get(f'/api/investigations/{inv_id}/history').json()
    assert all(row['payload']['condition_origin'] == origin for row in history)


def test_match_investigation_permissions_csrf_canonical_scope_and_validation(client, sign_in):
    asset, rule, match_id = match_fixture(client, sign_in)
    path = f'/api/condition-rules/matches/{match_id}/investigation'
    sign_in('planner')
    assert client.get(path).status_code == 403 and prepare(client, match_id).status_code == 403
    sign_in('admin')
    assert prepare(client, match_id, reason='   ').status_code == 422
    assert prepare(client, match_id, title='Invalid\ncontrol').status_code == 422
    client.headers.pop('X-CSRF-Token', None)
    assert prepare(client, match_id).status_code == 403
    with SessionLocal() as db:
        email = uuid.uuid4().hex+'@example.invalid'
        user = User(name='Scoped investigation engineer', email=email, role='engineer', sites=['Habshan Processing Hub'], password_hash=password_hash('Synthetic investigation password 2026!'))
        db.add(user); db.flush(); uid = user.id; db.commit()
    try:
        login = client.post('/api/auth/login', json={'email': email, 'password': 'Synthetic investigation password 2026!'})
        assert login.status_code == 200
        client.headers['X-CSRF-Token'] = login.json()['csrf']
        assert client.get(path).status_code == 404 and prepare(client, match_id).status_code == 404
    finally:
        with SessionLocal() as db:
            db.execute(delete(LoginSession).where(LoginSession.user_id == uid))
            db.execute(delete(SiteMembership).where(SiteMembership.user_id == uid))
            db.execute(delete(User).where(User.id == uid)); db.commit()


def test_match_investigation_rejects_inconsistent_link_without_exposing_other_equipment(client, sign_in):
    asset, rule, match_id = match_fixture(client, sign_in)
    with SessionLocal() as db:
        other = db.scalar(select(Asset).where(Asset.id != asset['id']))
        user = db.scalar(select(User).where(User.role == 'admin'))
        inv = Investigation(asset_id=other.id, creator_id=user.id, title='Inconsistent fixture', payload={}, payload_hash=payload_hash({}))
        db.add(inv); db.flush(); db.add(ConditionMatchInvestigation(match_id=match_id, investigation_id=inv.id)); db.commit()
    path = f'/api/condition-rules/matches/{match_id}/investigation'
    assert client.get(path).status_code == 409 and prepare(client, match_id).status_code == 409


@pytest.mark.parametrize('same_key', [False, True])
def test_concurrent_match_investigation_requests_create_one_record(client, sign_in, monkeypatch, same_key):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, local
    import backend.main as main
    asset, rule, match_id = match_fixture(client, sign_in)
    barrier, state, original_hash = Barrier(2), local(), main.payload_hash

    def synchronized_hash(body):
        if isinstance(body, dict) and set(body) == {'title', 'reason'} and not getattr(state, 'seen', False):
            state.seen = True
            barrier.wait(timeout=10)  # Align both requests before their initial receipt lookup.
        return original_hash(body)

    monkeypatch.setattr(main, 'payload_hash', synchronized_hash)
    keys = [str(uuid.uuid4()), str(uuid.uuid4())]
    if same_key: keys[1] = keys[0]
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda key: prepare(client, match_id, key=key), keys))
    assert [r.status_code for r in responses] == [201, 201], [r.text for r in responses]
    assert len({r.json()['investigation']['id'] for r in responses}) == 1
    if same_key: assert responses[0].json() == responses[1].json()
    else: assert sorted(r.json()['created'] for r in responses) == [False, True]
    with SessionLocal() as db:
        link = db.get(ConditionMatchInvestigation, match_id)
        assert link and db.scalar(select(func.count()).select_from(RecommendationRevision).where(RecommendationRevision.investigation_id == link.investigation_id)) == 1
