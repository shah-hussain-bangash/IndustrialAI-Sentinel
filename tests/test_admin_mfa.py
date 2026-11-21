import base64
import uuid
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select,delete,update
from backend.database import SessionLocal,User,Site,SiteMembership,LoginSession,MfaCredential,MfaChallenge,MfaPolicy,now
from backend.security import password_hash,token_hash
from backend.main import app,LOGIN_ATTEMPTS
from backend import accounts
from backend.mfa_core import totp,code_hash

PASSWORD='Administrator private fixture 84729!'

@pytest.fixture
def admin(client,monkeypatch):
    monkeypatch.setenv('SENTINEL_MFA_KEY',Fernet.generate_key().decode())
    accounts.ATTEMPTS.clear();LOGIN_ATTEMPTS.clear()
    with SessionLocal() as db:
        user=User(email=uuid.uuid4().hex+'@example.invalid',name='MFA fixture administrator',role='admin',password_hash=password_hash(PASSWORD),sites=list(db.scalars(select(Site.name))))
        db.add(user);db.commit();id=user.id;email=user.email
    r=client.post('/api/auth/login',json=dict(email=email,password=PASSWORD));assert r.status_code==200,r.text
    client.headers['X-CSRF-Token']=r.json()['csrf']
    yield dict(id=id,email=email)
    with SessionLocal() as db:
        db.execute(delete(MfaChallenge).where(MfaChallenge.user_id==id));db.execute(delete(MfaCredential).where(MfaCredential.user_id==id));db.execute(delete(LoginSession).where(LoginSession.user_id==id));db.execute(delete(SiteMembership).where(SiteMembership.user_id==id));db.execute(delete(User).where(User.id==id));db.execute(update(MfaPolicy).values(required=0));db.commit()

def enroll(client):
    result=client.post('/api/auth/mfa/enroll',json=dict(password=PASSWORD));assert result.status_code==200,result.text
    secret=result.json()['secret'];code=totp(secret,int(now()//30))
    confirmed=client.post('/api/auth/mfa/confirm',json=dict(code=code));assert confirmed.status_code==200,confirmed.text
    return secret,confirmed.json()['backup_codes']

@pytest.mark.parametrize('timestamp,expected',[(59,'94287082'),(1111111109,'07081804'),(1111111111,'14050471'),(1234567890,'89005924'),(2000000000,'69279037'),(20000000000,'65353130')])
def test_rfc6238_sha1_vectors(timestamp,expected):
    secret=base64.b32encode(b'12345678901234567890').decode().rstrip('=')
    assert totp(secret,timestamp//30,8)==expected

def test_enrollment_encryption_signin_backup_and_replay(client,admin):
    secret,codes=enroll(client)
    assert len(codes)==10 and len(set(codes))==10
    status=client.get('/api/auth/mfa/status').json();assert status['enrolled'] and status['session_verified']
    with SessionLocal() as db:
        credential=db.get(MfaCredential,admin['id']);assert secret not in credential.secret_encrypted and all(c not in str(credential.recovery_hashes) for c in codes)
    with TestClient(app) as other:
        login=other.post('/api/auth/login',json=dict(email=admin['email'],password=PASSWORD));assert login.json()['mfa_required'] and 'user' not in login.json()
        assert other.get('/api/assets').status_code==401
        # The enrollment code cannot be reused to sign in during the same step.
        verify=other.post('/api/auth/mfa/verify',json=dict(code=totp(secret,int(now()//30))),headers={'X-MFA-CSRF':login.json()['challenge_csrf']});assert verify.status_code==400
        valid=other.post('/api/auth/mfa/verify',json=dict(code=codes[0]),headers={'X-MFA-CSRF':login.json()['challenge_csrf']});assert valid.status_code==200,valid.text
        assert other.get('/api/assets').status_code==200
        assert other.post('/api/auth/mfa/verify',json=dict(code=codes[1]),headers={'X-MFA-CSRF':login.json()['challenge_csrf']}).status_code==401
    assert client.get('/api/auth/mfa/status').json()['backup_codes_remaining']==9
    with TestClient(app) as other:
        login=other.post('/api/auth/login',json=dict(email=admin['email'],password=PASSWORD))
        assert other.post('/api/auth/mfa/verify',json=dict(code=codes[0]),headers={'X-MFA-CSRF':login.json()['challenge_csrf']}).status_code==400

def test_challenge_expiry_attempts_csrf_and_account_changes(client,admin):
    secret,codes=enroll(client)
    with TestClient(app) as other:
        login=other.post('/api/auth/login',json=dict(email=admin['email'],password=PASSWORD));csrf=login.json()['challenge_csrf']
        assert other.post('/api/auth/mfa/verify',json=dict(code=codes[0])).status_code==403
        for _ in range(5):assert other.post('/api/auth/mfa/verify',json=dict(code='invalid'),headers={'X-MFA-CSRF':csrf}).status_code==400
        assert other.post('/api/auth/mfa/verify',json=dict(code=codes[0]),headers={'X-MFA-CSRF':csrf}).status_code==401
        login=other.post('/api/auth/login',json=dict(email=admin['email'],password=PASSWORD));csrf=login.json()['challenge_csrf']
        with SessionLocal() as db:db.execute(update(MfaChallenge).where(MfaChallenge.user_id==admin['id']).values(expires=now()-1));db.commit()
        assert other.post('/api/auth/mfa/verify',json=dict(code=codes[0]),headers={'X-MFA-CSRF':csrf}).status_code==401
        login=other.post('/api/auth/login',json=dict(email=admin['email'],password=PASSWORD));csrf=login.json()['challenge_csrf']
        with SessionLocal() as db:db.execute(update(User).where(User.id==admin['id']).values(role='disabled'));db.commit()
        assert other.post('/api/auth/mfa/verify',json=dict(code=codes[0]),headers={'X-MFA-CSRF':csrf}).status_code==401

def test_policy_requires_all_admins_and_blocks_unverified_sessions(client,admin):
    secret,codes=enroll(client)
    status=client.get('/api/auth/mfa/status').json()
    body=dict(password=PASSWORD,code=codes[0],required=True,expected_version=status['policy_version'])
    assert client.post('/api/auth/mfa/policy',json=body).status_code==409
    extra=[]
    try:
        with SessionLocal() as db:
            for id in db.scalars(select(User.id).where(User.role=='admin',User.id!=admin['id'])):
                db.add(MfaCredential(user_id=id,secret_encrypted=Fernet(__import__('os').environ['SENTINEL_MFA_KEY']).encrypt(b'JBSWY3DPEHPK3PXP').decode(),enabled=1,enrollment_expires=0,last_step=-1,recovery_hashes=[code_hash('A'*32)],version=1));extra.append(id)
            db.commit()
        enabled=client.post('/api/auth/mfa/policy',json=body);assert enabled.status_code==200,enabled.text
        assert client.post('/api/auth/mfa/disable',json=dict(password=PASSWORD,code=codes[1])).status_code==409
        with SessionLocal() as db:db.execute(update(LoginSession).where(LoginSession.user_id==admin['id']).values(mfa_verified=0));db.commit()
        assert client.get('/api/team').status_code==401
    finally:
        with SessionLocal() as db:db.execute(delete(MfaCredential).where(MfaCredential.user_id.in_(extra)));db.execute(update(MfaPolicy).values(required=0));db.commit()

def test_backup_rotation_removal_and_new_admin_gate(client,admin):
    secret,codes=enroll(client)
    rotated=client.post('/api/auth/mfa/backup-codes',json=dict(password=PASSWORD,code=codes[0]));assert rotated.status_code==200
    assert not set(codes)&set(rotated.json()['backup_codes'])
    removed=client.post('/api/auth/mfa/disable',json=dict(password=PASSWORD,code=rotated.json()['backup_codes'][0]));assert removed.status_code==200,removed.text
    assert client.get('/api/auth/me').status_code==401
    with SessionLocal() as db:db.execute(update(MfaPolicy).values(required=1));db.commit()
    login=client.post('/api/auth/login',json=dict(email=admin['email'],password=PASSWORD));assert login.status_code==200
    assert login.json()['user']['mfa_setup_required']
    client.headers['X-CSRF-Token']=login.json()['csrf']
    assert client.get('/api/assets').status_code==428
    assert client.get('/api/auth/mfa/status').status_code==200

def test_nonadmin_shared_password_and_missing_key(client,sign_in,admin,monkeypatch):
    monkeypatch.delenv('SENTINEL_MFA_KEY');monkeypatch.setenv('SENTINEL_MFA_KEY_FILE','nonexistent-private-key.fixture')
    assert not client.get('/api/auth/mfa/status').json()['key_ready']
    assert client.post('/api/auth/mfa/enroll',json=dict(password=PASSWORD)).status_code==503
    sign_in('engineer');assert client.get('/api/auth/mfa/status').status_code==403
    sign_in('admin');assert client.post('/api/auth/mfa/enroll',json=dict(password='SentinelDemo!2026')).status_code==422

def test_device_replacement_keeps_policy_and_requires_new_enrollment(client,admin):
    secret,codes=enroll(client)
    with SessionLocal() as db:db.execute(update(MfaPolicy).values(required=1));db.commit()
    replaced=client.post('/api/auth/mfa/replace-device',json=dict(password=PASSWORD,code=codes[0]));assert replaced.status_code==200,replaced.text
    assert client.get('/api/auth/me').status_code==401
    login=client.post('/api/auth/login',json=dict(email=admin['email'],password=PASSWORD));assert login.status_code==200 and login.json()['user']['mfa_setup_required']
    client.headers['X-CSRF-Token']=login.json()['csrf']
    assert client.get('/api/team').status_code==428
    newsecret,newcodes=enroll(client);assert newsecret!=secret and not set(newcodes)&set(codes)
    assert client.get('/api/team').status_code==200
