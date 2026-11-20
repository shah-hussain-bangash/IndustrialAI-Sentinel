import hashlib
import hmac
import secrets
import os
from fastapi import HTTPException, Request, Depends
from sqlalchemy.orm import Session
from .database import SessionLocal, LoginSession, User, Site, SiteMembership, now
from sqlalchemy import select
from sqlalchemy.orm.attributes import set_committed_value

COOKIE = "sentinel_session"
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "SentinelDemo!2026")
DEMO_ENABLED = os.getenv("DEMO_MODE", "true").lower() == "true"


def password_hash(password: str, salt: str | None = None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000).hex()
    return f"{salt}${digest}"


def password_valid(password, stored):
    salt, _ = stored.split("$", 1)
    return hmac.compare_digest(password_hash(password, salt), stored)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def get_db():
    with SessionLocal() as db:
        try:
            yield db
        except Exception:
            db.rollback()
            raise


def current_user(request: Request, db: Session = Depends(get_db)):
    raw = request.cookies.get(COOKIE, "")
    session = db.get(LoginSession, token_hash(raw)) if raw else None
    if not session or session.expires <= now():
        raise HTTPException(401, "Your session has expired. Please sign in again.")
    user = db.get(User, session.user_id)
    if not user or user.role in ('disabled', 'invited'):
        raise HTTPException(401, "Session user is unavailable.")
    canonicalize_user(user, db)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        if not hmac.compare_digest(request.headers.get("X-CSRF-Token", ""), session.csrf):
            raise HTTPException(
                403, "The session security token is missing. Refresh and try again."
            )
    request.state.user = user
    request.state.csrf = session.csrf
    return user


def canonicalize_user(user, db):
    sites = list(db.scalars(select(Site).join(SiteMembership, Site.id == SiteMembership.site_id).where(SiteMembership.user_id == user.id)))
    by_name = {s.name:s for s in sites}
    names = [name for name in user.sites if name in by_name]
    names += sorted(set(by_name)-set(names))
    set_committed_value(user, "sites", names)
    user._site_ids = [by_name[name].id for name in names]
    return user


def allow(user, *roles):
    if user.role not in roles:
        raise HTTPException(403, f'This action requires: {", ".join(roles)}.')


def site_allowed(user, site):
    if site not in user.sites:
        raise HTTPException(404, "This resource is not available in your workspace.")
