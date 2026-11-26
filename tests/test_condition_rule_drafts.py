import uuid
import pytest
from sqlalchemy import select, func
from backend.database import SessionLocal, ConditionRule, ConditionRuleRevision, Episode, Audit, Asset, User, SiteMembership, LoginSession
from backend.security import password_hash
from sqlalchemy import delete


def body(asset_id, **changes):
    return dict(asset_id=asset_id, channel="vibration", threshold=4.5, hysteresis=.2,
                persistence_seconds=30, maximum_gap_seconds=300, name="Pump vibration review", reason="Initial engineering draft", **changes)


def request(client, url, data, key=None):
    return client.post(url, json=data, headers={"Idempotency-Key": key or str(uuid.uuid4())})


def test_save_revise_history_stale_version_and_idempotent_retry(client, sign_in):
    sign_in("engineer")
    asset = client.get("/api/assets").json()[0]
    with SessionLocal() as db:
        episodes = db.scalar(select(func.count()).select_from(Episode))
        threshold = db.get(Asset, asset["id"]).threshold
    key = str(uuid.uuid4()); data = body(asset["id"])
    response = request(client, "/api/condition-rules/drafts", data, key)
    assert response.status_code == 201, response.text
    draft = response.json(); id = draft["id"]
    assert draft["state"] == "draft" and draft["active"] is False and draft["version"] == 1
    assert request(client, "/api/condition-rules/drafts", data, key).json() == draft
    changed = {**data, "threshold": 5, "reason": "Reviewed historical variability", "expected_version": 1}
    update_key = str(uuid.uuid4())
    saved = request(client, f"/api/condition-rules/drafts/{id}", changed, update_key)
    assert saved.status_code == 200, saved.text
    assert saved.json()["version"] == 2
    assert request(client, f"/api/condition-rules/drafts/{id}", changed, update_key).json() == saved.json()
    assert request(client, f"/api/condition-rules/drafts/{id}", changed).status_code == 409
    assert request(client, "/api/condition-rules/drafts", {**data, "name": "Different"}, key).status_code == 409
    history = client.get(f"/api/condition-rules/drafts/{id}/history").json()
    assert [v["version"] for v in history["items"]] == [2, 1]
    assert history["items"][1]["settings"]["threshold"] == 4.5
    assert history["items"][0]["settings"]["threshold"] == 5
    listing = client.get("/api/condition-rules/drafts", params={"asset_id": asset["id"]}).json()
    assert any(d["id"] == id and d["version"] == 2 for d in listing["items"])
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Episode)) == episodes
        assert db.get(Asset, asset["id"]).threshold == threshold
        assert db.scalar(select(func.count()).select_from(ConditionRuleRevision).where(ConditionRuleRevision.rule_id == id)) == 2
        logs = list(db.scalars(select(Audit).where(Audit.details.contains(id))))
        assert len(logs) == 2 and all(a.action == "Condition rule draft saved" for a in logs)


def test_draft_site_scope_and_roles(client, sign_in):
    sign_in("engineer")
    assets = client.get("/api/assets").json()
    other = next(a for a in assets if a["site"] == "Ruwais Energy Complex")
    draft = request(client, "/api/condition-rules/drafts", body(other["id"])).json()
    sign_in("restricted")
    for path in (f"/api/condition-rules/drafts?asset_id={other['id']}", f"/api/condition-rules/drafts/{draft['id']}/history"):
        assert client.get(path).status_code == 403
    assert request(client, "/api/condition-rules/drafts", body(other["id"])).status_code == 403
    sign_in("planner")
    assert request(client, f"/api/condition-rules/drafts/{draft['id']}", {**body(other["id"]), "expected_version": 1}).status_code == 403


def test_rule_cannot_move_equipment_and_rejects_activation(client, sign_in):
    sign_in("engineer")
    assets = client.get("/api/assets").json()
    draft = request(client, "/api/condition-rules/drafts", body(assets[0]["id"])).json()
    assert request(client, f"/api/condition-rules/drafts/{draft['id']}", {**body(assets[1]["id"]), "expected_version": 1}).status_code == 422
    assert request(client, "/api/condition-rules/drafts", {**body(assets[0]["id"]), "active": True}).status_code == 422
    for field in ("name", "reason"):
        assert request(client, "/api/condition-rules/drafts", {**body(assets[0]["id"]), field: "  "}).status_code == 422
    client.headers.pop("X-CSRF-Token", None)
    assert request(client, "/api/condition-rules/drafts", body(assets[0]["id"])).status_code == 403


def test_drafts_enforce_site_access_even_for_engineer(client, sign_in):
    sign_in("engineer")
    other = next(a for a in client.get("/api/assets").json() if a["site"] == "Ruwais Energy Complex")
    draft = request(client, "/api/condition-rules/drafts", body(other["id"])).json()
    with SessionLocal() as db:
        email = uuid.uuid4().hex + "@example.invalid"
        user = User(name="Restricted engineer", email=email, role="engineer", sites=["Habshan Processing Hub"],
                    password_hash=password_hash("Draft fixture password 2026!"))
        db.add(user); db.flush(); user_id = user.id; db.commit()
    try:
        login = client.post("/api/auth/login", json=dict(email=email, password="Draft fixture password 2026!"))
        client.headers["X-CSRF-Token"] = login.json()["csrf"]
        assert client.get("/api/condition-rules/drafts", params={"asset_id": other["id"]}).status_code in (403, 404)
        assert client.get(f"/api/condition-rules/drafts/{draft['id']}/history").status_code in (403, 404)
        assert request(client, "/api/condition-rules/drafts", body(other["id"])).status_code in (403, 404)
        assert request(client, f"/api/condition-rules/drafts/{draft['id']}", {**body(other["id"]), "expected_version": 1}).status_code in (403, 404)
    finally:
        with SessionLocal() as db:
            db.execute(delete(LoginSession).where(LoginSession.user_id == user_id))
            db.execute(delete(SiteMembership).where(SiteMembership.user_id == user_id))
            db.execute(delete(User).where(User.id == user_id)); db.commit()
