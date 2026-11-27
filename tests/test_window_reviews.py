import uuid
import pytest
from sqlalchemy import select, func
from backend.database import SessionLocal, MaintenanceWindowReview, User, ConditionRuleMatch
from test_maintenance_windows import clear_windows, body, create, equipment
from test_live_rules import cleanup_live_fixture, draft, control, ingest


def post(client, path, data, key=None):
    return client.post(path, json=data, headers={'Idempotency-Key': key or str(uuid.uuid4())})


def proposal(client, sign_in):
    asset = equipment(client, sign_in); data = body(asset); saved = create(client, data).json()
    return asset, data, saved, '/api/maintenance-windows/drafts/' + saved['id']


def decision(draft_version=1, review_version=0):
    return dict(decision='approved', expected_draft_version=draft_version, expected_review_version=review_version,
        reason='Independent synthetic planning review only', confirmed=True)


def test_independent_review_idempotency_and_revision_invalidates_decision(client, sign_in, clear_windows):
    asset, data, saved, path = proposal(client, sign_in)
    assert client.get(path + '/reviews').json()['can_review'] is False
    assert post(client, path + '/reviews', decision()).status_code == 403
    sign_in('admin'); before = client.get(path + '/reviews').json()
    assert before['can_review'] and before['current_decision'] is None and before['saved_revision']['name'] == data['name']
    key = str(uuid.uuid4()); response = post(client, path + '/reviews', decision(), key)
    assert response.status_code == 200, response.text
    assert response.json()['current_decision'] == 'approved'
    assert post(client, path + '/reviews', decision(), key).json() == response.json()
    assert post(client, path + '/reviews', {**decision(), 'reason': 'Different decision note'}, key).status_code == 409
    assert post(client, path + '/reviews', decision()).status_code == 409
    reject = post(client, path + '/reviews', {**decision(review_version=1), 'decision': 'rejected'})
    assert reject.status_code == 200 and reject.json()['review_version'] == 2
    sign_in('engineer')
    changed = post(client, path, {**data, 'expected_version': 1, 'reason': 'Revise interval for fresh review', 'ends_at': data['ends_at'] + 60})
    assert changed.status_code == 200
    pending = client.get(path + '/reviews').json()
    assert pending['current_decision'] is None and pending['last_review']['draft_version'] == 1
    assert [r['state'] for r in pending['items']] == ['rejected', 'approved']
    sign_in('admin'); assert post(client, path + '/reviews', decision(1, 2)).status_code == 409
    assert post(client, path + '/reviews', decision(2, 2)).status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(MaintenanceWindowReview)) == 3


def test_author_cannot_review_own_saved_revision(client, sign_in, clear_windows):
    asset = equipment(client, sign_in); sign_in('admin'); saved = create(client, body(asset)).json()
    path = '/api/maintenance-windows/drafts/' + saved['id'] + '/reviews'
    assert client.get(path).json()['can_review'] is False
    assert post(client, path, decision()).status_code == 403


@pytest.mark.parametrize('changes', [{'confirmed': False}, {'confirmed': 1}, {'reason': 'bad'}, {'reason': 'line\nbreak'},
    {'decision': 'active'}, {'expected_draft_version': True}, {'expected_review_version': -1}, {'activate': True}])
def test_review_validation(client, sign_in, clear_windows, changes):
    _, _, _, path = proposal(client, sign_in); sign_in('admin')
    assert post(client, path + '/reviews', {**decision(), **changes}).status_code == 422
    assert client.get(path + '/reviews').json()['review_version'] == 0


def test_review_site_role_anonymous_and_csrf(client, sign_in, clear_windows):
    _, _, _, path = proposal(client, sign_in); path += '/reviews'
    sign_in('admin'); client.headers.pop('X-CSRF-Token', None)
    assert post(client, path, decision()).status_code == 403
    sign_in('restricted'); assert client.get(path).status_code == 403
    sign_in('admin')
    from backend.main import app
    from backend.security import current_user
    with SessionLocal() as db:
        scoped = db.scalar(select(User).where(User.email == 'restricted@sentinel.local'))
        scoped.role = 'admin'
        app.dependency_overrides[current_user] = lambda: scoped
        try:
            assert client.get(path).status_code == 404
            assert post(client, path, decision()).status_code == 404
        finally: app.dependency_overrides.pop(current_user, None)
    client.cookies.clear(); assert client.get(path).status_code == 401


def test_review_pagination(client, sign_in, clear_windows):
    _, _, saved, path = proposal(client, sign_in)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == 'admin@sentinel.local'))
        for v in range(1, 62):
            db.add(MaintenanceWindowReview(draft_id=saved['id'], version=v, draft_version=1, state='approved' if v % 2 else 'rejected',
                actor_id=user.id, actor_name=user.name, reason='Synthetic history fixture'))
        db.commit()
    first = client.get(path + '/reviews').json()
    last = client.get(path + '/reviews', params={'before_version': first['next_before_version']}).json()
    assert len(first['items']) == 50 and len(last['items']) == 11 and last['next_before_version'] is None
    assert [r['version'] for r in first['items'] + last['items']] == list(range(61, 0, -1))


def test_approved_plan_does_not_suppress_rule_evaluation(client, sign_in, clear_windows):
    asset, rule = draft(client, sign_in, persistence=0)
    sign_in('engineer'); data = body(asset)
    from backend.database import now
    data.update(starts_at=int(now())-60, ends_at=int(now())+3600)
    saved = create(client, data).json(); sign_in('admin')
    assert post(client, '/api/maintenance-windows/drafts/' + saved['id'] + '/reviews', decision()).status_code == 200
    active = control(client, rule); assert active.status_code == 200
    assert ingest(client, asset, active.json()['activated_at'] + 1, 7).status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(ConditionRuleMatch).where(ConditionRuleMatch.rule_id == rule['id'])).state == 'active'
