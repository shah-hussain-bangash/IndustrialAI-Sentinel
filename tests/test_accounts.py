import uuid
import ssl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,update
from backend.main import app,LOGIN_ATTEMPTS
from backend.database import SessionLocal,AccountLink,User,now
from backend import accounts,account_email

PASSWORD='A private test-only password 63842!'

@pytest.fixture(autouse=True)
def mail(monkeypatch):
    accounts.ATTEMPTS.clear()
    sent=[]
    monkeypatch.setenv('SENTINEL_ACCOUNT_EMAIL_ENABLED','true')
    monkeypatch.setenv('SENTINEL_MAIL_SENDER','test@example.invalid')
    monkeypatch.setenv('SENTINEL_MAIL_APP_PASSWORD','abcdefghijklmnop')
    monkeypatch.setenv('SENTINEL_PUBLIC_URL','https://sentinel.example.invalid')
    monkeypatch.setattr(account_email,'send_link',lambda recipient,purpose,token:sent.append((recipient,purpose,token)))
    return sent

def invite(client):
    sites=client.get('/api/team').json()['sites']
    body=dict(name='Invitation fixture',email=uuid.uuid4().hex+'@example.invalid',role='approver',site_ids=[sites[0]['id']])
    response=client.post('/api/accounts/invite',json=body)
    assert response.status_code==201,response.text
    return body,response.json()

def test_invitation_activation_single_use_no_secret_storage(client,sign_in,mail):
    sign_in('admin');body,result=invite(client)
    assert len(mail)==1
    token=mail[0][2]
    assert token not in str(result)
    with SessionLocal() as db:
        member=db.get(User,result['id']);assert member.role=='invited'
        link=db.scalar(select(AccountLink).where(AccountLink.user_id==member.id))
        assert link.state=='sent' and token not in str(link.__dict__)
    info=client.post('/api/accounts/link-info',json=dict(token=token))
    assert info.status_code==200 and info.json()['purpose']=='invite'
    assert 'email' not in info.json()
    assert client.post('/api/accounts/set-password',json=dict(token=token,password='short')).status_code==422
    assert client.post('/api/accounts/set-password',json=dict(token=token,password='SentinelDemo!2026')).status_code==422
    response=client.post('/api/accounts/set-password',json=dict(token=token,password=PASSWORD))
    assert response.status_code==200,response.text
    assert client.post('/api/accounts/set-password',json=dict(token=token,password=PASSWORD+'new')).status_code==400
    with TestClient(app) as other:
        LOGIN_ATTEMPTS.clear();login=other.post('/api/auth/login',json=dict(email=body['email'],password=PASSWORD))
        assert login.status_code==200 and login.json()['user']['role']=='approver'
        assert other.get('/api/team').status_code==403

def test_reset_generic_response_revokes_sessions(client,sign_in,mail):
    sign_in('admin');body,result=invite(client)
    token=mail[-1][2]
    assert client.post('/api/accounts/set-password',json=dict(token=token,password=PASSWORD)).status_code==200
    with TestClient(app) as member:
        LOGIN_ATTEMPTS.clear();member.post('/api/auth/login',json=dict(email=body['email'],password=PASSWORD))
        requested=client.post('/api/accounts/forgot-password',json=dict(email=body['email']))
        missing=client.post('/api/accounts/forgot-password',json=dict(email='missing@example.invalid'))
        assert requested.status_code==missing.status_code==202 and requested.json()==missing.json()
        reset=mail[-1][2]
        assert mail[-1][1]=='reset'
        assert client.post('/api/accounts/set-password',json=dict(token=reset,password=PASSWORD)).status_code==422
        assert client.post('/api/accounts/set-password',json=dict(token=reset,password=PASSWORD+'changed')).status_code==200
        assert member.get('/api/auth/me').status_code==401
        assert client.post('/api/accounts/link-info',json=dict(token=reset)).status_code==400

def test_resend_expiry_disable_and_failed_mail(client,sign_in,mail,monkeypatch):
    sign_in('admin');body,result=invite(client);first=mail[-1][2]
    resend=client.post('/api/accounts/'+result['id']+'/resend-invitation',json={})
    assert resend.status_code==200
    assert client.post('/api/accounts/link-info',json=dict(token=first)).status_code==400
    second=mail[-1][2]
    with SessionLocal() as db:
        db.execute(update(AccountLink).where(AccountLink.token_hash==accounts.token_hash(second)).values(expires=now()-1));db.commit()
    assert client.post('/api/accounts/link-info',json=dict(token=second)).status_code==400
    assert client.post('/api/accounts/'+result['id']+'/resend-invitation',json={}).status_code==200
    third=mail[-1][2]
    member=next(m for m in client.get('/api/team').json()['items'] if m['id']==result['id'])
    response=client.put('/api/team/'+member['id'],json=dict(name=member['name'],role='disabled',site_ids=member['site_ids'],expected_version=member['version']))
    assert response.status_code==200
    assert client.post('/api/accounts/link-info',json=dict(token=third)).status_code==400
    def fail(*args):raise RuntimeError('private transport error')
    monkeypatch.setattr(account_email,'send_link',fail)
    body,failed=invite(client)
    statuses=client.get('/api/accounts/email-status').json()['deliveries']
    assert next(d for d in statuses if d['user_id']==failed['id'])['state']=='failed'
    assert 'private transport error' not in str(statuses)

def test_mail_permissions_and_public_configuration(client,sign_in,mail,monkeypatch):
    assert client.get('/api/accounts/email-status').status_code==401
    sign_in('restricted');assert client.get('/api/accounts/email-status').status_code==403
    sign_in('admin');body,result=invite(client)
    assert client.post('/api/accounts/invite',json={**body,'email':'new'+body['email'],'role':'admin'}).status_code==422
    client.headers.pop('X-CSRF-Token')
    assert client.post('/api/accounts/invite',json={**body,'email':'new'+body['email']}).status_code==403
    monkeypatch.setenv('SENTINEL_ACCOUNT_EMAIL_ENABLED','false')
    assert client.post('/api/accounts/forgot-password',json=dict(email=body['email'])).status_code==503
    for url in ['http://public.example.invalid','https://evil:secret@example.invalid','https://example.invalid/#bad','https://example.invalid/?bad=1']:
        monkeypatch.setenv('SENTINEL_ACCOUNT_EMAIL_ENABLED','true');monkeypatch.setenv('SENTINEL_PUBLIC_URL',url)
        assert not account_email.configuration()['ready']

def test_gmail_transport_requires_tls_and_never_embeds_password(monkeypatch):
    import importlib
    original=importlib.reload(account_email)
    calls=[]
    class SMTP:
        def __init__(self,host,port,timeout):assert (host,port)==('smtp.gmail.com',587)
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def ehlo(self):calls.append('ehlo')
        def starttls(self,context):assert isinstance(context,ssl.SSLContext);calls.append('tls')
        def login(self,*args):calls.append('login')
        def send_message(self,message):
            calls.append('send');assert 'abcdefghijklmnop' not in message.get_content();assert '/#account-link=' in message.get_content()
    monkeypatch.setattr(original.smtplib,'SMTP',SMTP)
    original.send_link('recipient@example.invalid','invite','x'*43)
    assert calls==['ehlo','tls','ehlo','login','send']
