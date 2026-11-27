import uuid
from sqlalchemy import select, func, delete
from backend.database import (SessionLocal, ConditionRuleMatch, ConditionRuleDeployment, ConditionRuleAssignment,
    ConditionRuleReview, ConditionMatchInvestigation, Investigation, Reading, Audit, WorkOrder, User, LoginSession, SiteMembership)
from backend.security import password_hash
from test_rule_reviews import match_fixture, review
from test_live_rules import call, cleanup_live_fixture


def counters():
    with SessionLocal() as db:
        models = [ConditionRuleMatch, ConditionRuleAssignment, ConditionRuleReview, Investigation, Audit, WorkOrder]
        return [db.scalar(select(func.count()).select_from(model)) for model in models]


def test_export_preserves_exact_trigger_revision_history_and_database(client, sign_in):
    asset, rule, mid = match_fixture(client, sign_in)
    assert call(client, f'/api/condition-rules/drafts/{rule["id"]}', {
        **rule['settings'], 'name': 'Later revision', 'threshold': 9,
        'expected_version': 1, 'reason': 'New inactive revision fixture'}).status_code == 200
    assert review(client, mid).status_code == 200
    assert review(client, mid, 'resolve', version=1, reason='Synthetic assessment only; no physical work.').status_code == 200
    before = counters()
    result = client.get(f'/api/condition-rules/matches/{mid}/export')
    assert result.status_code == 200, result.text
    assert result.headers['content-type'] == 'application/json'
    assert result.headers['cache-control'] == 'no-store'
    assert result.headers['x-content-type-options'] == 'nosniff'
    assert result.headers['content-disposition'] == f'attachment; filename="sentinel-condition-{mid}.json"'
    report = result.json()
    assert report['format_version'] == 1 and report['format'] == 'sentinel.condition-review'
    assert report['evidence']['match_id'] == mid
    assert report['evidence']['rule']['version'] == 1
    assert report['evidence']['rule']['settings']['threshold'] == rule['settings']['threshold']
    assert report['review']['current']['state'] == 'resolved'
    assert [r['version'] for r in report['review']['history_newest_first']] == [2, 1]
    assert report['review']['included_records'] == 2 and report['review']['truncated'] is False
    assert report['ownership']['current']['owner_id'] is None
    assert report['linked_investigation'] is None
    assert 'password_hash' not in result.text and 'mfa_secret' not in result.text and 'csrf' not in result.text
    assert counters() == before
    with SessionLocal() as db:
        match = db.get(ConditionRuleMatch, mid)
        assert report['evidence']['snapshot']['id'] == match.trigger_reading_id
        assert match.state == 'paused' and db.get(ConditionRuleDeployment, rule['id']).state == 'paused'


def test_export_role_site_and_session_checks(client, sign_in):
    asset, rule, mid = match_fixture(client, sign_in)
    path = f'/api/condition-rules/matches/{mid}/export'
    sign_in('planner'); assert client.get(path).status_code == 403
    sign_in('restricted'); assert client.get(path).status_code == 403
    with SessionLocal() as db:
        email = uuid.uuid4().hex + '@example.invalid'
        person = User(name='Export scoped fixture', email=email, role='engineer', sites=['Habshan Processing Hub'], password_hash=password_hash('Export fixture password 2026!'))
        db.add(person); db.flush(); uid = person.id; db.commit()
    try:
        assert client.post('/api/auth/login', json={'email': email, 'password': 'Export fixture password 2026!'}).status_code == 200
        denied = client.get(path)
        assert denied.status_code == 404 and asset['tag'] not in denied.text
        sign_in('admin'); assert client.get(path).status_code == 200
        assert client.get('/api/condition-rules/matches/missing/export').status_code == 404
        client.cookies.clear(); assert client.get(path).status_code == 401
    finally:
        with SessionLocal() as db:
            db.execute(delete(LoginSession).where(LoginSession.user_id == uid))
            db.execute(delete(SiteMembership).where(SiteMembership.user_id == uid))
            db.execute(delete(User).where(User.id == uid)); db.commit()


def test_export_bounds_history_and_explicitly_marks_omissions(client, sign_in):
    asset, rule, mid = match_fixture(client, sign_in)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.role == 'admin'))
        for version in range(1, 102):
            db.add(ConditionRuleAssignment(match_id=mid, version=version, owner_id=None, owner_name=None,
                actor_id=user.id, actor_name=user.name, reason=f'Assignment fixture {version}'))
        db.commit()
    result = client.get(f'/api/condition-rules/matches/{mid}/export')
    assert result.status_code == 200, result.text
    owner = result.json()['ownership']
    assert owner['total_records'] == 101 and owner['included_records'] == 100 and owner['truncated'] is True
    assert [r['version'] for r in owner['history_newest_first']] == list(range(101, 1, -1))
    assert owner['current']['version'] == 101


def test_export_rejects_cross_equipment_evidence(client, sign_in):
    asset, rule, mid = match_fixture(client, sign_in)
    with SessionLocal() as db:
        match = db.get(ConditionRuleMatch, mid); original = match.trigger_reading_id
        other = db.scalar(select(Reading).where(Reading.asset_id != asset['id']))
        match.trigger_reading_id = other.id; db.commit()
    try:
        result = client.get(f'/api/condition-rules/matches/{mid}/export')
        assert result.status_code == 409 and 'snapshot' not in result.json()
    finally:
        with SessionLocal() as db:
            db.get(ConditionRuleMatch, mid).trigger_reading_id = original; db.commit()


def test_export_conceals_inconsistent_link_and_handles_nonfinite_context(client, sign_in):
    asset, rule, mid = match_fixture(client, sign_in)
    with SessionLocal() as db:
        match = db.get(ConditionRuleMatch, mid)
        db.get(Reading, match.trigger_reading_id).temperature = float('inf')
        other = db.scalar(select(Investigation).where(Investigation.asset_id != asset['id']))
        assert other
        db.add(ConditionMatchInvestigation(match_id=mid, investigation_id=other.id)); db.commit()
    try:
        result = client.get(f'/api/condition-rules/matches/{mid}/export')
        assert result.status_code == 200, result.text
        report = result.json()
        assert report['linked_investigation'] == {'state': 'unavailable'}
        assert other.id not in result.text and other.title not in result.text
        assert next(row for row in report['evidence']['snapshot']['signals'] if row['channel'] == 'temperature')['value'] is None
    finally:
        with SessionLocal() as db:
            db.execute(delete(ConditionMatchInvestigation).where(ConditionMatchInvestigation.match_id == mid)); db.commit()
