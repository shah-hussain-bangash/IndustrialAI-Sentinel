import uuid
from sqlalchemy import select, delete
from backend.database import (SessionLocal, ConditionRuleMatch, ConditionMatchInvestigation, Investigation,
                              User, SiteMembership, LoginSession, Asset, now)
from backend.security import password_hash
from backend.seed import payload_hash
from test_live_rules import cleanup_live_fixture, call
from test_rule_reviews import match_fixture
from test_match_investigations import prepare


PATH = '/api/condition-rules/inbox'


def rows(client, state='all', **params):
    result = client.get(PATH, params={'review_state': 'all', 'investigation_state': state, **params})
    assert result.status_code == 200, result.text
    return result.json()


def test_inbox_tracks_live_investigation_review_approval_expiry_and_planning(client, sign_in):
    asset, rule, match_id = match_fixture(client, sign_in)
    assert match_id in [row['id'] for row in rows(client, 'not_started')['items']]
    inv = prepare(client, match_id).json()['investigation']
    inv_id = inv['id']
    first = next(row for row in rows(client, 'awaiting_review')['items'] if row['id'] == match_id)
    assert first['investigation']['id'] == inv_id and first['investigation']['version'] == 1
    assert first['signal_state'] == 'paused' and first['review']['state'] == 'unreviewed'
    assert match_id not in [row['id'] for row in rows(client, 'not_started')['items']]
    sign_in('approver')
    rejected = call(client, f'/api/investigations/{inv_id}/decision', dict(expected_version=1, decision='reject', reason='Return synthetic draft for review.'))
    assert rejected.status_code == 200, rejected.text
    sign_in('engineer')
    assert match_id in [row['id'] for row in rows(client, 'rejected')['items']]
    edited = client.patch(f'/api/investigations/{inv_id}', json=dict(expected_version=rejected.json()['version'],
                          recommendation='Review the synthetic signal and applicable controlled procedure.', checklist=['Check data quality and operating context.']), headers={'Idempotency-Key': str(uuid.uuid4())})
    assert edited.status_code == 200, edited.text
    assert match_id in [row['id'] for row in rows(client, 'awaiting_review')['items']]
    sign_in('approver')
    approved = call(client, f'/api/investigations/{inv_id}/decision', dict(expected_version=edited.json()['version'], decision='approve', reason='Synthetic fixture acceptance review.'))
    assert approved.status_code == 200, approved.text
    sign_in('admin')
    item = next(row for row in rows(client, 'approved')['items'] if row['id'] == match_id)
    assert item['investigation']['approval_current'] is True
    with SessionLocal() as db:
        db.get(Investigation, inv_id).approved_until = now() - 1; db.commit()
    assert match_id not in [row['id'] for row in rows(client, 'approved')['items']]
    expired = next(row for row in rows(client, 'approval_needed')['items'] if row['id'] == match_id)
    assert expired['investigation']['state'] == 'approved' and expired['investigation']['approval_current'] is False
    with SessionLocal() as db:
        current = db.get(Investigation, inv_id)
        current.approved_until = now() + 1000; current.approved_hash = 'outdated-hash'; db.commit()
    assert rows(client, 'approved')['total_matching'] == 0
    assert match_id in [row['id'] for row in rows(client, 'approval_needed')['items']]
    with SessionLocal() as db:
        current = db.get(Investigation, inv_id)
        current.approved_hash = current.payload_hash; current.approved_until = None; db.commit()
    assert match_id in [row['id'] for row in rows(client, 'approval_needed')['items']]
    with SessionLocal() as db:
        db.get(Investigation, inv_id).approved_until = now() + 1000; db.commit()
    planned = call(client, '/api/work-orders', dict(investigation_id=inv_id, expected_version=approved.json()['version'], due_date='2026-12-01'))
    assert planned.status_code == 201, planned.text
    planned_row = next(row for row in rows(client, 'dispatched')['items'] if row['id'] == match_id)
    assert planned_row['investigation']['state'] == 'dispatched' and not planned_row['investigation']['approval_current']


def test_inbox_investigation_filters_are_applied_before_cursor_pagination(client, sign_in):
    asset, rule, match_id = match_fixture(client, sign_in)
    with SessionLocal() as db:
        trigger = db.get(ConditionRuleMatch, match_id).trigger_reading_id
        creator = db.scalar(select(User.id).where(User.role == 'admin'))
        for index in range(61):
            match = ConditionRuleMatch(rule_id=rule['id'], rule_version=1, state='paused', started_at=1, triggered_at=2, ended_at=3, trigger_reading_id=trigger, created=12345)
            db.add(match); db.flush()
            inv = Investigation(asset_id=asset['id'], creator_id=creator, title='Pagination fixture', state='awaiting_review' if index < 51 else 'rejected', payload={}, payload_hash=payload_hash({}))
            db.add(inv); db.flush(); db.add(ConditionMatchInvestigation(match_id=match.id, investigation_id=inv.id))
        db.commit()
    first = rows(client, 'awaiting_review', site=asset['site'])
    assert first['total_matching'] == 51 and len(first['items']) == 50 and first['next_cursor']
    second = rows(client, 'awaiting_review', site=asset['site'], **first['next_cursor'])
    assert len(second['items']) == 1 and second['next_cursor'] is None
    assert len({row['id'] for row in first['items'] + second['items']}) == 51
    assert rows(client, 'not_started', site=asset['site'])['total_matching'] == 1
    assert client.get(PATH, params={'investigation_state': 'unknown'}).status_code == 422


def test_inbox_inconsistent_link_does_not_expose_other_equipment_investigation(client, sign_in):
    asset, rule, match_id = match_fixture(client, sign_in)
    with SessionLocal() as db:
        other = db.scalar(select(Asset).where(Asset.id != asset['id']))
        creator = db.scalar(select(User.id).where(User.role == 'admin'))
        inv = Investigation(asset_id=other.id, creator_id=creator, title='Private other-site fixture', payload={}, payload_hash=payload_hash({}))
        db.add(inv); db.flush(); db.add(ConditionMatchInvestigation(match_id=match_id, investigation_id=inv.id)); db.commit()
    item = next(row for row in rows(client, 'unavailable')['items'] if row['id'] == match_id)
    assert item['investigation'] == {'state': 'unavailable'}
    assert match_id not in [row['id'] for row in rows(client, 'not_started')['items']]
    assert match_id not in [row['id'] for row in rows(client, 'awaiting_review')['items']]


def test_inbox_investigation_scope_combined_filters_and_read_only_behavior(client, sign_in):
    asset, rule, match_id = match_fixture(client, sign_in)
    inv = prepare(client, match_id).json()['investigation']
    with SessionLocal() as db:
        before = (db.get(Investigation, inv['id']).payload_hash, db.get(Investigation, inv['id']).state,
                  db.get(Investigation, inv['id']).version, db.get(ConditionRuleMatch, match_id).state)
    sign_in('engineer')
    assert rows(client, 'awaiting_review', ownership='mine')['total_matching'] == 0
    assert match_id in [row['id'] for row in rows(client, 'awaiting_review', ownership='unassigned')['items']]
    assert rows(client, 'awaiting_review', review_state='resolved')['total_matching'] == 0
    sign_in('planner')
    assert client.get(PATH, params={'investigation_state': 'awaiting_review'}).status_code == 403
    with SessionLocal() as db:
        email = uuid.uuid4().hex+'@example.invalid'
        user = User(name='Scoped inbox fixture', email=email, role='engineer', sites=['Habshan Processing Hub'], password_hash=password_hash('Synthetic inbox password 2026!'))
        db.add(user); db.flush(); uid = user.id; db.commit()
    try:
        login = client.post('/api/auth/login', json={'email': email, 'password': 'Synthetic inbox password 2026!'})
        assert login.status_code == 200
        assert rows(client, 'awaiting_review')['total_matching'] == 0
        assert client.get(PATH, params={'site': asset['site'], 'investigation_state': 'awaiting_review'}).status_code == 403
    finally:
        with SessionLocal() as db:
            db.execute(delete(LoginSession).where(LoginSession.user_id == uid))
            db.execute(delete(SiteMembership).where(SiteMembership.user_id == uid))
            db.execute(delete(User).where(User.id == uid)); db.commit()
            after = (db.get(Investigation, inv['id']).payload_hash, db.get(Investigation, inv['id']).state,
                     db.get(Investigation, inv['id']).version, db.get(ConditionRuleMatch, match_id).state)
            assert before == after
