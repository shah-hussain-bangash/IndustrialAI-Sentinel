"""Single-company team administration using existing users and memberships."""
import hashlib
import json
import re
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from sqlalchemy import select, update, delete, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .database import User, Site, SiteMembership, Organization, LoginSession, Audit
from .security import current_user, get_db, password_hash, DEMO_PASSWORD

Role = Literal['admin', 'engineer', 'approver', 'planner', 'technician', 'observer', 'disabled']

class MemberInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=100)
    role: Role
    site_ids: list[str] = Field(min_length=1, max_length=200)

    @field_validator('name')
    @classmethod
    def clean(cls, value):
        if not value.strip() or any(ord(c) < 32 for c in value):
            raise ValueError('Enter a name without control characters.')
        return value.strip()

    @field_validator('site_ids')
    @classmethod
    def sites_valid(cls, values):
        if len(set(values)) != len(values) or any(not re.fullmatch(r'[a-zA-Z0-9-]{1,36}', x) for x in values):
            raise ValueError('Choose distinct available sites.')
        return values

class MemberCreate(MemberInput):
    email: str = Field(min_length=3, max_length=200)
    password: SecretStr

    @field_validator('email')
    @classmethod
    def email_valid(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r'[^\s@\x00-\x1f]+@[^\s@\x00-\x1f]+\.[^\s@\x00-\x1f]+', value):
            raise ValueError('Enter a valid email address.')
        return value

    @field_validator('password')
    @classmethod
    def password_valid(cls, value):
        raw = value.get_secret_value()
        if not 15 <= len(raw) <= 128 or not raw.strip() or raw == DEMO_PASSWORD:
            raise ValueError('Choose a unique password of 15–128 characters, different from the shared demo password.')
        return value

class MemberUpdate(MemberInput):
    expected_version: str = Field(pattern=r'^[a-f0-9]{64}$')

def create_team_router():
    router = APIRouter(prefix='/api/team', tags=['Team and site access'])

    def memberships(db, user):
        return sorted(db.scalars(select(SiteMembership.site_id).where(SiteMembership.user_id == user.id)))

    def full_admin(db, user):
        sites = list(db.scalars(select(Site).order_by(Site.name)))
        if user.role != 'admin' or set(memberships(db, user)) != {s.id for s in sites}:
            raise HTTPException(403, 'Team administration requires an administrator assigned to every site.')
        return sites

    def serialize(db, user):
        ids = memberships(db, user)
        # Opaque optimistic-concurrency token; never return stored password hashes.
        version = hashlib.sha256(json.dumps([user.id, user.name, user.email, user.role, ids, user.password_hash]).encode()).hexdigest()
        return dict(id=user.id, name=user.name, email=user.email, role=user.role, active=user.role not in ('disabled', 'invited'), site_ids=ids, version=version)

    def lock_company(db):
        row = db.get(Organization, 'primary')
        if not row:
            raise HTTPException(503, 'Apply the organization foundation first.')
        changed = db.execute(update(Organization).where(Organization.id == 'primary', Organization.version == row.version).values(version=Organization.version + 1).execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            raise HTTPException(409, 'Company access changed. Refresh before saving.')

    def check_sites(sites, body):
        if not set(body.site_ids) <= {s.id for s in sites}:
            raise HTTPException(422, 'Choose available sites only.')

    def audit(db, actor, sites, action, target, before, after):
        # No passwords, password hashes or version tokens in audit records.
        details = json.dumps(dict(actor_id=actor.id, before=before, after=after), sort_keys=True)
        for site in sites:
            db.add(Audit(site=site.name, site_id=site.id, actor=actor.name, action=action, target=target.id, details=details))

    def public_state(member):
        return {key: member[key] for key in ('name', 'email', 'role', 'site_ids')}

    @router.get('')
    def directory(user: User = Depends(current_user), db: Session = Depends(get_db)):
        sites = full_admin(db, user)
        return dict(items=[serialize(db, u) for u in db.scalars(select(User).order_by(User.name))], sites=[dict(id=s.id, name=s.display_name) for s in sites], current_user_id=user.id)

    @router.post('', status_code=201)
    def create(body: MemberCreate, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
        sites = full_admin(db, user)
        check_sites(sites, body)
        if body.role == 'disabled':
            raise HTTPException(422, 'Create an active account first.')
        lock_company(db)
        if db.scalar(select(User.id).where(func.lower(User.email) == body.email)):
            raise HTTPException(409, 'An account with this email already exists.')
        member = User(email=body.email, name=body.name, role=body.role, password_hash=password_hash(body.password.get_secret_value()), sites=[s.name for s in sites if s.id in body.site_ids])
        try:
            db.add(member); db.flush()
            result = serialize(db, member)
            audit(db, user, [s for s in sites if s.id in body.site_ids], 'Team member created', member, None, public_state(result))
            db.commit()
            return result
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, 'Account changed. Refresh the team directory.')

    @router.put('/{id}')
    def edit(id: str, body: MemberUpdate, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
        sites = full_admin(db, user)
        check_sites(sites, body)
        if id == user.id:
            raise HTTPException(403, 'Your own access is protected. Ask another company administrator to change it.')
        lock_company(db)
        member = db.get(User, id)
        if not member:
            raise HTTPException(404, 'Team member not found.')
        db.refresh(member)
        if body.role == 'admin':
            from .mfa_core import required
            from .security import DEMO_PASSWORD,password_valid
            if required(db) and password_valid(DEMO_PASSWORD,member.password_hash):
                raise HTTPException(409,'This person must set a personal password before administrator access can be granted under the MFA policy.')
        if member.role == 'invited' and body.role != 'disabled':
            raise HTTPException(409, 'Pending accounts must accept their invitation before role changes. You may disable this invitation instead.')
        before = serialize(db, member)
        if before['version'] != body.expected_version:
            raise HTTPException(409, 'This account changed. Refresh and review its latest access.')
        # Conditional write also catches simultaneous password changes.
        result = db.execute(update(User).where(User.id == id, User.password_hash == member.password_hash, User.role == member.role, User.name == member.name).values(name=body.name, role=body.role, sites=[s.name for s in sites if s.id in body.site_ids]).execution_options(synchronize_session=False))
        if result.rowcount != 1:
            raise HTTPException(409, 'This account changed. Refresh before saving.')
        db.execute(delete(SiteMembership).where(SiteMembership.user_id == id))
        db.add_all([SiteMembership(user_id=id, site_id=site) for site in body.site_ids])
        db.execute(delete(LoginSession).where(LoginSession.user_id == id))
        db.flush(); db.refresh(member)
        after = serialize(db, member)
        relevant = set(before['site_ids']) | set(after['site_ids'])
        audit(db, user, [s for s in sites if s.id in relevant], 'Team access updated', member, public_state(before), public_state(after))
        db.commit()
        return after

    return router
