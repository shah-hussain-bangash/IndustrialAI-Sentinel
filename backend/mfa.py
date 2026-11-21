"""Administrator MFA enrollment, password-plus-code sign-in and reviewed rollout."""
import base64
import hmac
import io
import os
import secrets
from urllib.parse import quote,urlencode
import qrcode
import qrcode.image.svg
from fastapi import APIRouter,Depends,HTTPException,Request,Response
from pydantic import BaseModel,ConfigDict,SecretStr,Field
from sqlalchemy import select,update,delete
from sqlalchemy.orm import Session
from .database import User,LoginSession,MfaCredential,MfaChallenge,MfaPolicy,Site,SiteMembership,now
from .security import current_user,get_db,password_valid,token_hash,COOKIE,DEMO_PASSWORD,canonicalize_user
from .accounts import version,audit,limit
from .mfa_core import cipher,decrypt,consume,required,code_hash

CHALLENGE_COOKIE='sentinel_mfa_pending'

class PasswordInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    password:SecretStr=Field(min_length=1,max_length=200)
class Proof(PasswordInput):
    code:SecretStr=Field(min_length=1,max_length=64)
class CodeInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    code:SecretStr=Field(min_length=1,max_length=64)
class PolicyInput(Proof):
    required:bool
    expected_version:int=Field(ge=1)

def login_challenge(db,user,request,response):
    raw=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(24)
    db.execute(delete(MfaChallenge).where(MfaChallenge.user_id==user.id))
    previous=request.cookies.get(COOKIE)
    if previous:db.execute(delete(LoginSession).where(LoginSession.token_hash==token_hash(previous)))
    db.add(MfaChallenge(token_hash=token_hash(raw),user_id=user.id,csrf=csrf,account_version=version(db,user),expires=now()+300,attempts=0));db.commit()
    response.delete_cookie(COOKIE,path='/')
    response.set_cookie(CHALLENGE_COOKIE,raw,httponly=True,samesite='strict',secure=os.getenv('COOKIE_SECURE','false')=='true',max_age=300,path='/')
    return dict(mfa_required=True,challenge_csrf=csrf,message='Enter the code from your authenticator app or an unused backup code.')

def create_mfa_router(user_json):
    router=APIRouter(prefix='/api/auth/mfa',tags=['Administrator MFA'])

    def administrator(user):
        if user.role!='admin':raise HTTPException(403,'Authenticator enrollment currently applies to administrators only.')

    def password_check(user,raw):
        if len(raw)>200 or not password_valid(raw,user.password_hash):raise HTTPException(403,'Your current password is incorrect.')
        if raw==DEMO_PASSWORD:raise HTTPException(422,'Set a personal password in Account & password before enrolling MFA. The shared demo password cannot protect an administrator account.')

    def credential(db,user):
        row=db.get(MfaCredential,user.id)
        if not row or not row.enabled:raise HTTPException(409,'Enroll and verify your authenticator first.')
        return row

    def full_admin(db,user):
        administrator(user)
        if set(db.scalars(select(Site.id)))!=set(db.scalars(select(SiteMembership.site_id).where(SiteMembership.user_id==user.id))):raise HTTPException(403,'Company MFA policy requires an administrator assigned to every site.')

    @router.get('/status')
    def status(request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
        administrator(user)
        row=db.get(MfaCredential,user.id);policy=db.get(MfaPolicy,'primary')
        ready=True
        try:cipher()
        except HTTPException:ready=False
        admins=list(db.scalars(select(User).where(User.role=='admin')))
        enrolled=set(db.scalars(select(MfaCredential.user_id).where(MfaCredential.enabled==1)))
        can_policy=set(db.scalars(select(Site.id)))==set(db.scalars(select(SiteMembership.site_id).where(SiteMembership.user_id==user.id)))
        return dict(enrolled=bool(row and row.enabled),backup_codes_remaining=len(row.recovery_hashes) if row and row.enabled else 0,key_ready=ready,required=bool(policy and policy.required),policy_version=policy.version if policy else 1,can_manage_policy=can_policy,admin_count=len(admins) if can_policy else None,admins_enrolled=sum(u.id in enrolled for u in admins) if can_policy else None,session_verified=bool(request.state.session.mfa_verified),personal_password=not password_valid(DEMO_PASSWORD,user.password_hash))

    @router.post('/enroll')
    def enroll(body:PasswordInput,request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
        administrator(user);limit('mfa-enroll:'+user.id,5,600);password_check(user,body.password.get_secret_value())
        row=db.get(MfaCredential,user.id)
        if row and row.enabled:raise HTTPException(409,'An authenticator is already enrolled. Use your backup codes if the device is unavailable.')
        secret=base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')
        encrypted=cipher().encrypt(secret.encode()).decode()
        if row:
            row.secret_encrypted=encrypted;row.enrollment_expires=now()+600;row.version+=1
        else:db.add(MfaCredential(user_id=user.id,secret_encrypted=encrypted,enabled=0,enrollment_expires=now()+600,last_step=-1,recovery_hashes=[],version=1))
        db.commit()
        uri='otpauth://totp/'+quote('IndustrialAI Sentinel',safe='')+':'+quote(user.email,safe='')+'?'+urlencode(dict(secret=secret,issuer='IndustrialAI Sentinel',algorithm='SHA1',digits=6,period=30))
        qr=qrcode.make(uri,image_factory=qrcode.image.svg.SvgPathFillImage)
        return dict(secret=secret,qr_svg_base64=base64.b64encode(qr.to_string()).decode(),expires_in=600)

    @router.post('/confirm')
    def confirm(body:CodeInput,request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
        administrator(user);limit('mfa-confirm:'+user.id,10,600)
        row=db.get(MfaCredential,user.id)
        if not row or row.enabled or row.enrollment_expires<=now():raise HTTPException(400,'Setup expired or already completed. Start a new enrollment.')
        consume(db,row,body.code.get_secret_value(),now(),allow_backup=False)
        codes=[secrets.token_hex(16).upper() for _ in range(10)]
        db.execute(update(MfaCredential).where(MfaCredential.user_id==user.id).values(enabled=1,recovery_hashes=[code_hash(c) for c in codes]))
        db.execute(delete(LoginSession).where(LoginSession.user_id==user.id,LoginSession.token_hash!=request.state.session.token_hash))
        db.execute(update(LoginSession).where(LoginSession.token_hash==request.state.session.token_hash).values(mfa_verified=1))
        db.execute(delete(MfaChallenge).where(MfaChallenge.user_id==user.id))
        audit(db,user,'Administrator MFA enrolled');db.commit()
        return dict(message='Authenticator confirmed. Save the backup codes privately; they are shown only once.',backup_codes=['-'.join(c[i:i+8] for i in range(0,32,8)) for c in codes])

    @router.post('/verify')
    def verify(body:CodeInput,request:Request,response:Response,db:Session=Depends(get_db)):
        ip=request.client.host if request.client else 'local';limit('mfa-signin:'+ip,30,600)
        raw=request.cookies.get(CHALLENGE_COOKIE,'')
        row=db.get(MfaChallenge,token_hash(raw)) if raw else None
        if not row or row.expires<=now() or row.attempts>=5:raise HTTPException(401,'Verification expired or too many attempts. Sign in with your password again.')
        if not hmac.compare_digest(row.csrf,request.headers.get('X-MFA-CSRF','')):raise HTTPException(403,'Verification token missing. Sign in again.')
        user=db.get(User,row.user_id)
        if not user or user.role in ('disabled','invited') or version(db,user)!=row.account_version:raise HTTPException(401,'Account changed. Sign in again.')
        updated=db.execute(update(MfaChallenge).where(MfaChallenge.token_hash==row.token_hash,MfaChallenge.attempts==row.attempts,MfaChallenge.attempts<5).values(attempts=row.attempts+1).execution_options(synchronize_session=False))
        if updated.rowcount!=1:raise HTTPException(409,'Verification changed. Try signing in again.')
        try:consume(db,credential(db,user),body.code.get_secret_value(),now())
        except HTTPException:
            db.commit() # failed attempts remain counted
            raise
        removed=db.execute(delete(MfaChallenge).where(MfaChallenge.token_hash==row.token_hash))
        if removed.rowcount!=1:raise HTTPException(409,'Verification already used. Sign in again.')
        token=secrets.token_urlsafe(36);csrf=secrets.token_urlsafe(24)
        db.add(LoginSession(token_hash=token_hash(token),user_id=user.id,csrf=csrf,expires=now()+28800,mfa_verified=1))
        audit(db,user,'Administrator MFA sign-in');db.commit()
        response.delete_cookie(CHALLENGE_COOKIE,path='/')
        response.set_cookie(COOKIE,token,httponly=True,samesite='strict',secure=os.getenv('COOKIE_SECURE','false')=='true',max_age=28800,path='/')
        return dict(user=user_json(canonicalize_user(user,db)),csrf=csrf)

    @router.post('/backup-codes')
    def backups(body:Proof,user:User=Depends(current_user),db:Session=Depends(get_db)):
        administrator(user);limit('mfa-backups:'+user.id,5,600);password_check(user,body.password.get_secret_value())
        row=credential(db,user);consume(db,row,body.code.get_secret_value(),now())
        codes=[secrets.token_hex(16).upper() for _ in range(10)]
        db.execute(update(MfaCredential).where(MfaCredential.user_id==user.id).values(recovery_hashes=[code_hash(c) for c in codes]))
        audit(db,user,'MFA backup codes replaced');db.commit()
        return dict(backup_codes=['-'.join(c[i:i+8] for i in range(0,32,8)) for c in codes])

    @router.post('/disable')
    def disable(body:Proof,user:User=Depends(current_user),db:Session=Depends(get_db)):
        administrator(user);limit('mfa-disable:'+user.id,5,600);password_check(user,body.password.get_secret_value())
        if required(db):raise HTTPException(409,'Company policy requires administrator MFA. An authorized company administrator must change the policy first.')
        row=credential(db,user);consume(db,row,body.code.get_secret_value(),now())
        db.execute(delete(MfaCredential).where(MfaCredential.user_id==user.id))
        db.execute(delete(LoginSession).where(LoginSession.user_id==user.id));db.execute(delete(MfaChallenge).where(MfaChallenge.user_id==user.id))
        audit(db,user,'Administrator MFA removed');db.commit()
        return dict(message='MFA removed. All sessions were revoked. Sign in again.')

    @router.post('/replace-device')
    def replace_device(body:Proof,user:User=Depends(current_user),db:Session=Depends(get_db)):
        administrator(user);limit('mfa-replace:'+user.id,5,600);password_check(user,body.password.get_secret_value())
        row=credential(db,user);consume(db,row,body.code.get_secret_value(),now())
        if not required(db):raise HTTPException(409,'During optional rollout, remove your authenticator and set it up again to change devices.')
        db.execute(update(MfaCredential).where(MfaCredential.user_id==user.id).values(enabled=0,enrollment_expires=0,recovery_hashes=[],last_step=-1))
        db.execute(delete(LoginSession).where(LoginSession.user_id==user.id));db.execute(delete(MfaChallenge).where(MfaChallenge.user_id==user.id))
        audit(db,user,'Administrator MFA device replacement started');db.commit()
        return dict(message='Old device and backup codes revoked. Sign in with your password; company policy will restrict access until the replacement authenticator is enrolled.')

    @router.post('/policy')
    def policy(body:PolicyInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
        full_admin(db,user);limit('mfa-policy:'+user.id,5,600);password_check(user,body.password.get_secret_value())
        row=credential(db,user)
        if body.required:
            ids=list(db.scalars(select(User.id).where(User.role=='admin')))
            enrolled=set(db.scalars(select(MfaCredential.user_id).where(MfaCredential.enabled==1)))
            if not set(ids)<=enrolled:raise HTTPException(409,'Enroll every current administrator before requiring MFA company-wide.')
        consume(db,row,body.code.get_secret_value(),now())
        result=db.execute(update(MfaPolicy).where(MfaPolicy.id=='primary',MfaPolicy.version==body.expected_version).values(required=int(body.required),version=MfaPolicy.version+1))
        if result.rowcount!=1:raise HTTPException(409,'MFA policy changed. Refresh and review it again.')
        audit(db,user,'Administrator MFA policy updated');db.commit()
        return dict(required=body.required,version=body.expected_version+1)

    return router
