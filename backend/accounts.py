"""Account invitations and password recovery, with no raw tokens in storage."""
import hashlib
import json
import secrets
import time
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import Session
from .database import AccountLink, User, Site, SiteMembership, Organization, LoginSession, Audit, SessionLocal, now
from .security import current_user, get_db, token_hash, password_hash, DEMO_PASSWORD, password_valid
from .team import MemberInput
from . import account_email

ATTEMPTS=defaultdict(list)
GENERIC='If this email belongs to an active account, a password-reset link will be sent. Check your inbox and spam folder.'

class EmailInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    email: str=Field(min_length=3,max_length=200)
    @field_validator('email')
    @classmethod
    def clean(cls,value):
        from .team import MemberCreate
        return MemberCreate.email_valid(value)

class InviteInput(MemberInput,EmailInput): pass

class TokenInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    token: SecretStr
    @field_validator('token')
    @classmethod
    def valid(cls,value):
        import re
        if not re.fullmatch(r'[A-Za-z0-9_-]{43}',value.get_secret_value()): raise ValueError('This link is invalid. Request a new link.')
        return value

class RedeemInput(TokenInput):
    password: SecretStr
    @field_validator('password')
    @classmethod
    def valid_password(cls,value):
        from .team import MemberCreate
        return MemberCreate.password_valid(value)

def version(db,user):
    sites=sorted(db.scalars(select(SiteMembership.site_id).where(SiteMembership.user_id==user.id)))
    return hashlib.sha256(json.dumps([user.id,user.name,user.email,user.role,sites,user.password_hash]).encode()).hexdigest()

def audit(db,user,action,target=None):
    sites=list(db.scalars(select(Site).join(SiteMembership,Site.id==SiteMembership.site_id).where(SiteMembership.user_id==user.id)))
    for site in sites:db.add(Audit(site=site.name,site_id=site.id,actor=user.name,action=action,target=target or user.id,details='Account email workflow. Credentials and link tokens omitted.'))

def limit(key,count,seconds):
    t=now()
    if len(ATTEMPTS)>5000:
        for k in list(ATTEMPTS):
            if not ATTEMPTS[k] or max(ATTEMPTS[k])<t-3600:ATTEMPTS.pop(k,None)
        if len(ATTEMPTS)>5000:raise HTTPException(429,'Too many requests. Try again later.')
    values=ATTEMPTS[key];values[:]=[v for v in values if v>t-seconds]
    if len(values)>=count:raise HTTPException(429,'Too many requests. Try again later.')
    values.append(t)

def issue(db,user,purpose,intended_role):
    # New requests supersede old links. Account changes also invalidate fingerprints.
    db.execute(update(AccountLink).where(AccountLink.user_id==user.id,AccountLink.purpose==purpose,AccountLink.state.in_(['pending','sent'])).values(state='revoked'))
    raw=secrets.token_urlsafe(32)
    row=AccountLink(token_hash=token_hash(raw),user_id=user.id,purpose=purpose,intended_role=intended_role,account_version=version(db,user),expires=now()+(86400 if purpose=='invite' else 1800),state='pending')
    db.add(row);db.flush()
    return row,raw

def deliver(digest,raw):
    with SessionLocal() as db:
        row=db.get(AccountLink,digest)
        if not row or row.state!='pending' or row.expires<=now():return
        user=db.get(User,row.user_id)
        if not user or version(db,user)!=row.account_version:
            row.state='revoked';db.commit();return
        try:
            account_email.send_link(user.email,row.purpose,raw)
            state='sent'
        except Exception:
            # Never log SMTP exception text; it may contain credentials or recipient details.
            state='failed'
        db.execute(update(AccountLink).where(AccountLink.token_hash==digest,AccountLink.state=='pending').values(state=state))
        db.commit()

def create_account_router():
    router=APIRouter(prefix='/api/accounts',tags=['Account invitation and recovery'])

    def administrator(db,user):
        sites=list(db.scalars(select(Site).order_by(Site.name)))
        ids=set(db.scalars(select(SiteMembership.site_id).where(SiteMembership.user_id==user.id)))
        if user.role!='admin' or ids!={s.id for s in sites}:raise HTTPException(403,'Account email administration requires an administrator assigned to every site.')
        return sites

    def configured():
        if not account_email.configuration()['ready']:raise HTTPException(503,'Account email is not configured. Ask your company administrator to configure Gmail delivery.')

    @router.get('/email-status')
    def email_status(user:User=Depends(current_user),db:Session=Depends(get_db)):
        administrator(db,user)
        rows=list(db.scalars(select(AccountLink).order_by(AccountLink.created.desc()).limit(50)))
        return dict(**account_email.status(),deliveries=[dict(id=r.token_hash[:12],user_id=r.user_id,purpose=r.purpose,state=r.state,created=r.created,expires=r.expires) for r in rows])

    @router.post('/invite',status_code=201)
    def invite(body:InviteInput,request:Request,tasks:BackgroundTasks,user:User=Depends(current_user),db:Session=Depends(get_db)):
        sites=administrator(db,user);configured()
        if body.role in ('disabled','admin'):
            raise HTTPException(422,'Invite a non-administrator role. An existing full-company administrator can grant administrator access after activation.')
        if not set(body.site_ids)<={s.id for s in sites}:raise HTTPException(422,'Choose available sites only.')
        limit('invite:'+user.id,20,3600)
        org=db.get(Organization,'primary')
        if not org:raise HTTPException(503,'Organization foundation is missing.')
        changed=db.execute(update(Organization).where(Organization.id=='primary',Organization.version==org.version).values(version=Organization.version+1))
        if changed.rowcount!=1:raise HTTPException(409,'Company changed. Refresh and retry.')
        if db.scalar(select(User.id).where(func.lower(User.email)==body.email)):raise HTTPException(409,'This email already has an account. Use Resend invitation for a pending account, or password recovery for an active account.')
        member=User(email=body.email,name=body.name,role='invited',sites=[s.name for s in sites if s.id in body.site_ids],password_hash=password_hash(secrets.token_urlsafe(48)))
        db.add(member);db.flush()
        row,raw=issue(db,member,'invite',body.role);audit(db,user,'Account invitation requested',member.id);db.commit()
        tasks.add_task(deliver,row.token_hash,raw)
        return dict(id=member.id,message='Invitation queued. Check delivery status; the user must open the email and set a password before signing in.')

    @router.post('/{id}/resend-invitation')
    def resend(id:str,request:Request,tasks:BackgroundTasks,user:User=Depends(current_user),db:Session=Depends(get_db)):
        administrator(db,user);configured();limit('resend:'+user.id,20,3600)
        member=db.get(User,id)
        if not member or member.role!='invited':raise HTTPException(409,'Only pending invitations can be resent.')
        previous=db.scalar(select(AccountLink).where(AccountLink.user_id==id,AccountLink.purpose=='invite').order_by(AccountLink.created.desc()))
        if not previous:raise HTTPException(409,'Original invitation is missing. Ask an administrator to review the account.')
        row,raw=issue(db,member,'invite',previous.intended_role);audit(db,user,'Account invitation resent',member.id);db.commit()
        tasks.add_task(deliver,row.token_hash,raw)
        return dict(message='Replacement invitation queued. Previous links no longer work.')

    @router.post('/forgot-password',status_code=202)
    def forgot(body:EmailInput,request:Request,tasks:BackgroundTasks,db:Session=Depends(get_db)):
        configured()
        ip=request.client.host if request.client else 'local'
        limit('forgot-ip:'+ip,15,3600)
        key='forgot-email:'+token_hash(body.email)
        # Per-address throttling gives the same generic response for every account state.
        try:limit(key,3,3600)
        except HTTPException:return dict(message=GENERIC)
        member=db.scalar(select(User).where(func.lower(User.email)==body.email))
        if member and member.role not in ('disabled','invited'):
            row,raw=issue(db,member,'reset',member.role);db.commit()
            tasks.add_task(deliver,row.token_hash,raw)
        return dict(message=GENERIC)

    def link(db,token):
        row=db.get(AccountLink,token_hash(token))
        member=db.get(User,row.user_id) if row else None
        if not row or not member or row.state!='sent' or row.expires<=now() or version(db,member)!=row.account_version or member.role=='disabled' or row.purpose=='invite' and member.role!='invited' or row.purpose=='reset' and member.role=='invited':
            raise HTTPException(400,'This link is invalid, expired or already used. Request a new link.')
        return row,member

    @router.post('/link-info')
    def info(body:TokenInput,request:Request,db:Session=Depends(get_db)):
        limit('link-info:'+(request.client.host if request.client else 'local'),60,60)
        row,member=link(db,body.token.get_secret_value())
        return dict(purpose=row.purpose,expires=row.expires)

    @router.post('/set-password')
    def redeem(body:RedeemInput,request:Request,db:Session=Depends(get_db)):
        limit('redeem:'+(request.client.host if request.client else 'local'),20,600)
        row,member=link(db,body.token.get_secret_value())
        new=body.password.get_secret_value()
        if password_valid(new,member.password_hash):raise HTTPException(422,'Enter a new password different from your current password.')
        consumed=db.execute(update(AccountLink).where(AccountLink.token_hash==row.token_hash,AccountLink.state=='sent',AccountLink.expires>now()).values(state='used'))
        if consumed.rowcount!=1:raise HTTPException(409,'This link has already been used. Request a new one.')
        changed=db.execute(update(User).where(User.id==member.id,User.password_hash==member.password_hash,User.role==member.role).values(password_hash=password_hash(new),role=row.intended_role).execution_options(synchronize_session=False))
        if changed.rowcount!=1:raise HTTPException(409,'Account changed. Request a new link.')
        db.execute(update(AccountLink).where(AccountLink.user_id==member.id,AccountLink.state.in_(['sent','pending'])).values(state='revoked'))
        db.execute(delete(LoginSession).where(LoginSession.user_id==member.id))
        audit(db,member,'Invitation accepted' if row.purpose=='invite' else 'Password reset completed')
        db.commit()
        return dict(message='Password saved. Sign in with your email and new password.')

    return router
