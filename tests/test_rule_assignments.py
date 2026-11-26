import uuid
import pytest
from sqlalchemy import select, delete, func
from backend.database import (SessionLocal, User, SiteMembership, Site, ConditionRuleAssignment, ConditionRuleMatch,
                              ConditionRuleDeployment, Audit, WorkOrder, LoginSession)
from backend.security import password_hash
from test_live_rules import cleanup_live_fixture, call
from test_rule_reviews import match_fixture, review


def owner_id(role):
    with SessionLocal() as db: return db.scalar(select(User.id).where(User.email == role + '@sentinel.local'))


def assign(client, match_id, owner, version=0, reason='Synthetic review assignment test.', key=None):
    return call(client, f'/api/condition-rules/matches/{match_id}/ownership',
                dict(owner_id=owner, expected_version=version, reason=reason), key)


def test_assignment_reassignment_clear_idempotency_stale_version_and_inbox(client, sign_in):
    asset, rule, match_id = match_fixture(client, sign_in)
    path = f'/api/condition-rules/matches/{match_id}/ownership'
    engineer, admin = owner_id('engineer'), owner_id('admin')
    with SessionLocal() as db: orders = db.scalar(select(func.count()).select_from(WorkOrder))
    initial = client.get(path).json()
    assert initial['current']['version'] == 0 and initial['current']['owner_id'] is None
    assert engineer in [p['id'] for p in initial['reviewers']]
    key = str(uuid.uuid4())
    first = assign(client, match_id, engineer, key=key)
    assert first.status_code == 200, first.text
    assert assign(client, match_id, engineer, key=key).json() == first.json()
    assert assign(client, match_id, admin).status_code == 409
    assert assign(client, match_id, engineer, version=1).status_code == 409
    sign_in('engineer')
    inbox = '/api/condition-rules/inbox'
    assert match_id in [r['id'] for r in client.get(inbox, params={'ownership': 'mine'}).json()['items']]
    assert match_id not in [r['id'] for r in client.get(inbox, params={'ownership': 'unassigned'}).json()['items']]
    assert assign(client, match_id, admin, version=1).status_code == 200
    assert match_id not in [r['id'] for r in client.get(inbox, params={'ownership': 'mine'}).json()['items']]
    assert assign(client, match_id, None, version=2).status_code == 200
    assert match_id in [r['id'] for r in client.get(inbox, params={'ownership': 'unassigned'}).json()['items']]
    history = client.get(path).json()
    assert [r['version'] for r in history['items']] == [3, 2, 1]
    assert [r['owner_id'] for r in history['items']] == [None, admin, engineer]
    assert history['current']['owner_id'] is None
    assert client.get(inbox, params={'ownership': 'unknown'}).status_code == 422
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(WorkOrder)) == orders
        assert db.get(ConditionRuleMatch, match_id).state == 'paused'
        assert db.get(ConditionRuleDeployment, rule['id']).state == 'paused'
        assert db.scalar(select(func.count()).select_from(Audit).where(Audit.action == 'Condition review ownership changed', Audit.target == asset['tag'])) == 3


@pytest.mark.parametrize('revoke', ['membership', 'role'])
def test_assignment_eligibility_uses_canonical_memberships_and_flags_lost_access(client, sign_in, revoke):
    asset, rule, match_id = match_fixture(client, sign_in)
    with SessionLocal() as db:
        email = uuid.uuid4().hex+'@example.invalid'
        user = User(name='Temporary eligible reviewer', email=email, role='engineer',
                    sites=[asset['site']], password_hash=password_hash('Synthetic fixture password 2026!'))
        db.add(user); db.flush(); uid = user.id
        site_id = db.scalar(select(Site.id).where(Site.name == asset['site'])); db.commit()
    try:
        assert assign(client, match_id, uid).status_code == 200
        with SessionLocal() as db:
            if revoke == 'membership':
                db.execute(delete(SiteMembership).where(SiteMembership.user_id == uid, SiteMembership.site_id == site_id))
            else: db.get(User, uid).role = 'disabled'
            db.commit()
            assert asset['site'] in db.get(User, uid).sites  # Deliberately stale compatibility cache.
        history = client.get(f'/api/condition-rules/matches/{match_id}/ownership').json()
        assert not history['owner_eligible'] and uid not in [p['id'] for p in history['reviewers']]
        row = next(r for r in client.get('/api/condition-rules/inbox').json()['items'] if r['id'] == match_id)
        assert row['ownership']['owner_id'] == uid and not row['ownership']['eligible']
        assert assign(client, match_id, None, version=1).status_code == 200
        assert assign(client, match_id, uid, version=2).status_code == 422
        if revoke == 'membership':
            login = client.post('/api/auth/login', json={'email': email, 'password': 'Synthetic fixture password 2026!'})
            assert login.status_code == 200
            client.headers['X-CSRF-Token'] = login.json()['csrf']
            assert client.get(f'/api/condition-rules/matches/{match_id}/ownership').status_code == 404
            assert assign(client, match_id, owner_id('admin'), version=2).status_code == 404
    finally:
        with SessionLocal() as db:
            db.execute(delete(ConditionRuleAssignment).where(ConditionRuleAssignment.owner_id == uid))
            db.execute(delete(LoginSession).where(LoginSession.user_id == uid))
            db.execute(delete(SiteMembership).where(SiteMembership.user_id == uid))
            db.execute(delete(User).where(User.id == uid)); db.commit()


def test_assignment_permissions_validation_csrf_and_search(client, sign_in):
    asset, rule, match_id = match_fixture(client, sign_in)
    engineer = owner_id('engineer')
    path = f'/api/condition-rules/matches/{match_id}/ownership'
    sign_in('planner')
    assert client.get(path).status_code == 403
    assert assign(client, match_id, engineer).status_code == 403
    sign_in('restricted')
    assert client.get(path).status_code == 403
    sign_in('admin')
    assert assign(client, match_id, owner_id('planner')).status_code == 422
    assert assign(client, match_id, 'missing').status_code == 422
    assert assign(client, match_id, None).status_code == 409
    assert assign(client, match_id, engineer, reason='  ').status_code == 422
    assert assign(client, match_id, engineer, reason='Invalid\nnote').status_code == 422
    assert client.get(path, params={'reviewer_name': '%'}).json()['reviewers'] == []
    candidates = client.get(path, params={'reviewer_name': 'Alex'}).json()['reviewers']
    assert candidates and all('Alex' in row['name'] for row in candidates)
    client.headers.pop('X-CSRF-Token', None)
    assert assign(client, match_id, engineer).status_code == 403


def test_resolved_review_retains_owner_and_rejects_assignment_change(client, sign_in):
    asset, rule, match_id = match_fixture(client, sign_in)
    engineer = owner_id('engineer')
    assert assign(client, match_id, engineer).status_code == 200
    assert review(client, match_id).status_code == 200
    assert review(client, match_id, 'resolve', version=1).status_code == 200
    assert assign(client, match_id, None, version=1).status_code == 409
    history = client.get(f'/api/condition-rules/matches/{match_id}/ownership').json()
    assert history['review_state'] == 'resolved'
    assert history['current']['owner_id'] == engineer and history['current']['version'] == 1


def test_assignment_history_is_bounded_and_paginates(client, sign_in):
    asset, rule, match_id = match_fixture(client, sign_in)
    admin = owner_id('admin')
    with SessionLocal() as db:
        for version in range(1, 53):
            db.add(ConditionRuleAssignment(match_id=match_id, version=version, owner_id=admin if version % 2 else None,
                       owner_name='Synthetic owner' if version % 2 else None, actor_id=admin, actor_name='Fixture admin', reason='Synthetic history test.'))
        db.commit()
    path = f'/api/condition-rules/matches/{match_id}/ownership'
    first = client.get(path).json()
    assert first['current']['version'] == 52 and len(first['items']) == 50 and first['next_before_version'] == 3
    second = client.get(path, params={'before_version': first['next_before_version']}).json()
    assert [row['version'] for row in second['items']] == [2, 1]
    assert second['current']['version'] == 52 and second['next_before_version'] is None
