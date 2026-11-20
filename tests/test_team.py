import uuid
from fastapi.testclient import TestClient
from sqlalchemy import select, delete
from backend.main import app, LOGIN_ATTEMPTS
from backend.database import SessionLocal, User, SiteMembership, LoginSession

PASSWORD = 'Private fixture passphrase 9846!'

def create(client):
    sites = client.get('/api/team').json()['sites']
    body = dict(name='Team fixture', email=uuid.uuid4().hex+'@example.invalid', role='observer', site_ids=[sites[0]['id']], password=PASSWORD)
    result = client.post('/api/team', json=body)
    assert result.status_code == 201, result.text
    assert 'password' not in result.json() and 'password_hash' not in result.json()
    return result.json(), body

def test_team_auth_scoping_and_validation(client, sign_in):
    assert client.get('/api/team').status_code == 401
    for role in ['observer', 'engineer', 'planner', 'approver', 'technician']:
        sign_in('restricted' if role=='observer' else role)
        assert client.get('/api/team').status_code == 403
    sign_in('admin')
    member, body = create(client)
    assert client.post('/api/team', json=body).status_code == 409
    for values in [dict(email='invalid'), dict(password='short'), dict(password='SentinelDemo!2026'), dict(site_ids=[]), dict(role='owner')]:
        assert client.post('/api/team', json={**body, **values}).status_code == 422
    assert client.post('/api/team', json={**body, 'email':'x'+body['email'], 'site_ids':[str(uuid.uuid4())]}).status_code == 422
    client.headers.pop('X-CSRF-Token')
    assert client.post('/api/team', json={**body,'email':'x'+body['email']}).status_code == 403

def test_team_lifecycle_revocation_stale_and_disable(client, sign_in):
    sign_in('admin'); member, body = create(client)
    with TestClient(app) as other:
        LOGIN_ATTEMPTS.clear()
        logged = other.post('/api/auth/login',json=dict(email=body['email'],password=PASSWORD))
        assert logged.status_code == 200
        assets = other.get('/api/assets').json()
        assert all(a['site_id'] in body['site_ids'] for a in assets)
        update = dict(name='Updated name', role='engineer', site_ids=body['site_ids'], expected_version=member['version'])
        saved = client.put('/api/team/'+member['id'],json=update)
        assert saved.status_code == 200, saved.text
        assert other.get('/api/auth/me').status_code == 401
        assert client.put('/api/team/'+member['id'],json=update).status_code == 409
        disabled = client.put('/api/team/'+member['id'],json={**update, 'role':'disabled', 'expected_version':saved.json()['version']})
        assert disabled.status_code == 200
        LOGIN_ATTEMPTS.clear()
        assert other.post('/api/auth/login',json=dict(email=body['email'],password=PASSWORD)).status_code == 401
        restored = client.put('/api/team/'+member['id'],json={**update,'expected_version':disabled.json()['version']})
        assert restored.status_code == 200
        LOGIN_ATTEMPTS.clear()
        assert other.post('/api/auth/login',json=dict(email=body['email'],password=PASSWORD)).status_code == 200
    audit = client.get('/api/activity').json()
    events=[e for e in audit if e['target']==member['id']]
    assert events and all(PASSWORD not in e['details'] and 'password_hash' not in e['details'] for e in events)

def test_self_protection_and_partial_admin(client, sign_in):
    current = sign_in('admin')
    directory = client.get('/api/team').json()
    member = next(m for m in directory['items'] if m['id']==current['id'])
    body = dict(name=member['name'], role='observer', site_ids=member['site_ids'], expected_version=member['version'])
    assert client.put('/api/team/'+member['id'],json=body).status_code == 403
    with SessionLocal() as db:
        partial=User(email=uuid.uuid4().hex+'@example.invalid',name='Scoped admin',role='admin',password_hash=__import__('backend.security',fromlist=['password_hash']).password_hash(PASSWORD),sites=[])
        db.add(partial);db.flush();db.add(SiteMembership(user_id=partial.id,site_id=member['site_ids'][0]));db.commit()
        email=partial.email
    LOGIN_ATTEMPTS.clear()
    login=client.post('/api/auth/login',json=dict(email=email,password=PASSWORD));assert login.status_code==200
    client.headers['X-CSRF-Token']=login.json()['csrf']
    assert client.get('/api/team').status_code==403
    assert client.post('/api/team',json=dict(name='Blocked',role='observer',site_ids=member['site_ids'],email='blocked@example.invalid',password=PASSWORD)).status_code==403
