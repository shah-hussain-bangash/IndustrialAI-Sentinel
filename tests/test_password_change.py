import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.database import Audit, LoginSession, SessionLocal, User, uid
from backend.main import app
from backend.security import COOKIE, password_hash, password_valid

OLD = "SentinelDemo!2026"


@pytest.fixture
def account(client):
    with SessionLocal() as db:
        existing = db.scalar(select(User))
        user = User(
            email=f"password-{uid()}@sentinel.local",
            name="Password test",
            role="observer",
            sites=existing.sites,
            password_hash=password_hash(OLD),
        )
        db.add(user)
        db.commit()
        return {"id": user.id, "email": user.email, "hash": user.password_hash}


def login(client, account, password=OLD):
    result = client.post("/api/auth/login", json={"email": account["email"], "password": password})
    assert result.status_code == 200, result.text
    client.headers["X-CSRF-Token"] = result.json()["csrf"]


def test_change_requires_authentication(client):
    assert client.post("/api/auth/password", json={"current_password": OLD, "new_password": "unique-long-test-passphrase"}).status_code == 401


def test_change_requires_csrf(client, account):
    login(client, account)
    client.headers.pop("X-CSRF-Token")
    assert client.post("/api/auth/password", json={"current_password": OLD, "new_password": "unique-long-test-passphrase"}).status_code == 403
    assert client.get("/api/auth/me").status_code == 200


@pytest.mark.parametrize("current,new,status", [
    ("wrong", "unique-long-test-passphrase", 403),
    (OLD, "too-short", 422),
    (OLD, " " * 15, 422),
    (OLD, "x" * 129, 422),
    (OLD, OLD, 422),
])
def test_rejected_changes_preserve_password_and_session(client, account, current, new, status):
    login(client, account)
    result = client.post("/api/auth/password", json={"current_password": current, "new_password": new})
    assert result.status_code == status
    assert client.get("/api/auth/me").status_code == 200
    with SessionLocal() as db:
        assert db.get(User, account["id"]).password_hash == account["hash"]


def test_change_revokes_sessions_removes_demo_access_and_keeps_other_accounts(client, account):
    login(client, account)
    other_browser = TestClient(app)
    login(other_browser, account)
    control = TestClient(app)
    result = control.post("/api/auth/login", json={"email": "admin@sentinel.local", "password": OLD})
    assert result.status_code == 200
    new = secrets.token_urlsafe(24)
    assert account["email"] in [u["email"] for u in client.get("/api/auth/demo").json()["accounts"]]
    result = client.post("/api/auth/password", json={"current_password": OLD, "new_password": new})
    assert result.status_code == 200
    assert COOKIE not in client.cookies
    assert client.get("/api/auth/me").status_code == 401
    assert other_browser.get("/api/auth/me").status_code == 401
    assert control.get("/api/auth/me").status_code == 200
    assert account["email"] not in [u["email"] for u in client.get("/api/auth/demo").json()["accounts"]]
    assert client.post("/api/auth/login", json={"email": account["email"], "password": OLD}).status_code == 401
    login(client, account, new)
    with SessionLocal() as db:
        user = db.get(User, account["id"])
        assert user.password_hash != account["hash"]
        assert new not in user.password_hash
        assert password_valid(new, user.password_hash)
        sessions = list(db.scalars(select(LoginSession).where(LoginSession.user_id == user.id)))
        assert len(sessions) == 1  # Only the new login survives.
        events = list(db.scalars(select(Audit).where(Audit.target == user.email)))
        assert events and all(e.action == "Password changed" for e in events)
        assert all(new not in e.details and OLD not in e.details for e in events)


def test_password_attempts_are_limited(client, account):
    login(client, account)
    for _ in range(5):
        assert client.post("/api/auth/password", json={"current_password": "wrong", "new_password": "unique-long-test-passphrase"}).status_code == 403
    assert client.post("/api/auth/password", json={"current_password": OLD, "new_password": "unique-long-test-passphrase"}).status_code == 429


def test_cannot_restore_shared_demo_password_or_reuse_current(client, account):
    login(client, account)
    new = secrets.token_urlsafe(24)
    assert client.post("/api/auth/password", json={"current_password": OLD, "new_password": new}).status_code == 200
    login(client, account, new)
    for candidate in (new, OLD):
        assert client.post("/api/auth/password", json={"current_password": new, "new_password": candidate}).status_code == 422
