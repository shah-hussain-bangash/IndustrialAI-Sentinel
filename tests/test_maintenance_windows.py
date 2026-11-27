import uuid
import pytest
from sqlalchemy import select, delete, func
from backend.database import (SessionLocal, MaintenanceWindowDraft, MaintenanceWindowRevision, MaintenanceWindowReview, MaintenanceWindowControl, MaintenanceWindowSuppression, Asset, User, LoginSession, SiteMembership,
    ConditionRuleDeployment, ConditionRuleMatch, ConditionRuleReview, WorkOrder, Audit, Reading, now)
from backend.security import password_hash
from test_live_rules import cleanup_live_fixture, draft, control, ingest


@pytest.fixture(autouse=True)
def clear_windows(cleanup_live_fixture):
    yield
    with SessionLocal() as db:
        db.execute(delete(MaintenanceWindowSuppression)); db.execute(delete(MaintenanceWindowControl)); db.execute(delete(MaintenanceWindowReview)); db.execute(delete(MaintenanceWindowRevision)); db.execute(delete(MaintenanceWindowDraft)); db.commit()


def body(asset):
    start = int(now()) + 3600
    return dict(asset_id=asset['id'], name='Synthetic maintenance plan', starts_at=start, ends_at=start + 7200,
        reason='Draft planning fixture only; no operational change.')


def create(client, data, key=None):
    return client.post('/api/maintenance-windows/drafts', json=data, headers={'Idempotency-Key': key or str(uuid.uuid4())})


def equipment(client, sign_in):
    sign_in('engineer')
    return next(asset for asset in client.get('/api/assets').json() if asset['site'] == 'Ruwais Energy Complex')


def test_window_create_revision_idempotency_and_audit(client, sign_in):
    asset = equipment(client, sign_in); original = body(asset); key = str(uuid.uuid4())
    first = create(client, original, key); assert first.status_code == 201, first.text
    saved = first.json(); assert saved['state'] == 'draft' and saved['active'] is False and saved['version'] == 1
    assert create(client, original, key).json() == saved
    assert create(client, {**original, 'name': 'Changed'}, key).status_code == 409
    revision = {**original, 'name': 'Revised plan', 'expected_version': 1, 'reason': 'Changed proposed duration for review', 'ends_at': original['ends_at'] + 60}
    path = '/api/maintenance-windows/drafts/' + saved['id']; revise_key = str(uuid.uuid4())
    response = client.post(path, json=revision, headers={'Idempotency-Key': revise_key})
    assert response.status_code == 200 and response.json()['version'] == 2, response.text
    assert client.post(path, json=revision, headers={'Idempotency-Key': revise_key}).json() == response.json()
    assert client.post(path, json=revision, headers={'Idempotency-Key': str(uuid.uuid4())}).status_code == 409
    history = client.get(path + '/history').json()['items']
    assert [row['version'] for row in history] == [2, 1]
    assert history[1]['name'] == original['name'] and history[1]['ends_at'] == original['ends_at']
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(MaintenanceWindowRevision).where(MaintenanceWindowRevision.draft_id == saved['id'])) == 2
        assert db.scalar(select(func.count()).select_from(Audit).where(Audit.action == 'Maintenance window draft saved', Audit.target == asset['tag'], Audit.details.contains(saved['id']))) == 2


def test_window_drafts_do_not_suppress_snapshots_or_change_existing_work(client, sign_in):
    asset, rule = draft(client, sign_in, persistence=0)
    with SessionLocal() as db:
        before = [db.scalar(select(func.count()).select_from(model)) for model in (Reading, ConditionRuleMatch, ConditionRuleReview, WorkOrder)]
    start = int(now()) - 60
    data = {**body(asset), 'starts_at': start, 'ends_at': start + 3600}
    assert create(client, data).status_code == 201
    with SessionLocal() as db:
        assert before == [db.scalar(select(func.count()).select_from(model)) for model in (Reading, ConditionRuleMatch, ConditionRuleReview, WorkOrder)]
        assert db.get(ConditionRuleDeployment, rule['id']) is None
    active = control(client, rule); assert active.status_code == 200
    assert ingest(client, asset, active.json()['activated_at'] + 1, 7).status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(ConditionRuleMatch).where(ConditionRuleMatch.rule_id == rule['id'])).state == 'active'


@pytest.mark.parametrize('changes', [{'name': ' '}, {'reason': 'bad'}, {'name': 'Bad\nname'}, {'starts_at': -1}, {'starts_at': True},
    {'starts_at': 1.5}, {'starts_at': 100, 'ends_at': 100}, {'starts_at': 100, 'ends_at': 604901}, {'active': True}, {'ends_at': 4102444801}])
def test_window_validation_rejects_invalid_content(client, sign_in, changes):
    asset = equipment(client, sign_in)
    assert create(client, {**body(asset), **changes}).status_code == 422
    assert not client.get('/api/maintenance-windows/drafts', params={'asset_id': asset['id']}).json()['items']


def test_window_roles_site_isolation_csrf_and_immutable_equipment(client, sign_in):
    asset = equipment(client, sign_in); data = body(asset); result = create(client, data).json()
    path = '/api/maintenance-windows/drafts/' + result['id']
    other_asset = next(item for item in client.get('/api/assets').json() if item['id'] != asset['id'])
    assert client.post(path, json={**data, 'asset_id': other_asset['id'], 'expected_version': 1}, headers={'Idempotency-Key': str(uuid.uuid4())}).status_code == 422
    client.headers.pop('X-CSRF-Token', None); assert create(client, data).status_code == 403
    sign_in('planner'); assert create(client, data).status_code == 403
    assert client.get(path + '/history').status_code == 403
    with SessionLocal() as db:
        email = uuid.uuid4().hex + '@example.invalid'
        person = User(email=email, name='Scoped window planner', role='engineer', sites=['Habshan Processing Hub'], password_hash=password_hash('Window fixture password 2026!'))
        db.add(person); db.flush(); uid = person.id; db.commit()
    try:
        login = client.post('/api/auth/login', json={'email': email, 'password': 'Window fixture password 2026!'})
        assert login.status_code == 200; client.headers['X-CSRF-Token'] = login.json()['csrf']
        assert client.get(path + '/history').status_code == 404
        assert client.get('/api/maintenance-windows/drafts', params={'asset_id': asset['id']}).status_code == 404
        assert create(client, data).status_code == 404
        client.cookies.clear(); assert client.get(path + '/history').status_code == 401
    finally:
        with SessionLocal() as db:
            db.execute(delete(LoginSession).where(LoginSession.user_id == uid)); db.execute(delete(SiteMembership).where(SiteMembership.user_id == uid)); db.execute(delete(User).where(User.id == uid)); db.commit()


def test_window_history_pagination_preserves_all_revisions(client, sign_in):
    asset = equipment(client, sign_in); saved = create(client, body(asset)).json()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.role == 'engineer'))
        for version in range(2, 62):
            db.add(MaintenanceWindowRevision(draft_id=saved['id'], version=version, name='History fixture', starts_at=100, ends_at=200,
                actor_id=user.id, actor_name=user.name, reason='Synthetic pagination fixture'))
        db.get(MaintenanceWindowDraft, saved['id']).version = 61; db.commit()
    path = '/api/maintenance-windows/drafts/' + saved['id'] + '/history'
    first = client.get(path).json(); second = client.get(path, params={'before_version': first['next_before_version']}).json()
    assert len(first['items']) == 50 and len(second['items']) == 11 and second['next_before_version'] is None
    assert [row['version'] for row in first['items'] + second['items']] == list(range(61, 0, -1))


def test_window_create_bound_prevents_unlimited_drafts(client, sign_in):
    asset = equipment(client, sign_in)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.role == 'engineer'))
        for _ in range(100):
            row = MaintenanceWindowDraft(asset_id=asset['id'], version=1); db.add(row); db.flush()
            db.add(MaintenanceWindowRevision(draft_id=row.id, version=1, name='Bound fixture', starts_at=100, ends_at=200,
                actor_id=user.id, actor_name=user.name, reason='Synthetic bounded listing fixture'))
        db.commit()
    assert len(client.get('/api/maintenance-windows/drafts', params={'asset_id': asset['id']}).json()['items']) == 100
    assert create(client, body(asset)).status_code == 422


def test_window_upgrade_from_0016_preserves_existing_rows_and_repeats(tmp_path):
    import sqlite3
    from test_sensor_upgrade import environment, legacy, run
    env, path = environment(tmp_path); legacy(env)
    run(env, '-m', 'alembic', 'upgrade', '0016')
    with sqlite3.connect(path) as db:
        names = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'alembic_version'")]
        original = {name: db.execute('SELECT * FROM "' + name + '" ORDER BY 1').fetchall() for name in names}
    run(env, 'scripts/upgrade_database.py', '--check-only'); run(env, 'scripts/upgrade_database.py')
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == '0019'
        for name, rows in original.items(): assert db.execute('SELECT * FROM "' + name + '" ORDER BY 1').fetchall() == rows, name
        assert db.execute('SELECT count(*) FROM maintenance_window_drafts').fetchone()[0] == 0
        assert db.execute('SELECT count(*) FROM maintenance_window_revisions').fetchone()[0] == 0
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    run(env, 'scripts/upgrade_database.py'); run(env, '-m', 'alembic', 'check')
