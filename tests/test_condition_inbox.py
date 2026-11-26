import uuid
from sqlalchemy import select, delete
from backend.database import SessionLocal, ConditionRuleMatch, User, SiteMembership, LoginSession
from backend.security import password_hash
from test_live_rules import cleanup_live_fixture
from test_rule_reviews import match_fixture, review


def test_inbox_filters_current_review_state_and_is_read_only(client, sign_in):
    asset, rule, match_id = match_fixture(client, sign_in)
    path = "/api/condition-rules/inbox"
    first = client.get(path)
    assert first.status_code == 200, first.text
    item = next(row for row in first.json()["items"] if row["id"] == match_id)
    assert item["review"]["state"] == "unreviewed" and item["signal_state"] == "paused"
    assert item["asset_tag"] == asset["tag"] and item["rule_version"] == 1
    assert review(client, match_id).status_code == 200
    assert match_id not in [r["id"] for r in client.get(path).json()["items"]]
    acknowledged = client.get(path, params={"review_state": "acknowledged"}).json()
    assert match_id in [r["id"] for r in acknowledged["items"]]
    assert review(client, match_id, "resolve", version=1).status_code == 200
    assert match_id in [r["id"] for r in client.get(path, params={"review_state": "resolved"}).json()["items"]]
    with SessionLocal() as db: assert db.get(ConditionRuleMatch, match_id).state == "paused"


def test_inbox_pagination_handles_equal_timestamps_without_missing_or_repeating(client, sign_in):
    asset, rule, match_id = match_fixture(client, sign_in)
    with SessionLocal() as db:
        original = db.get(ConditionRuleMatch, match_id)
        for i in range(55):
            db.add(ConditionRuleMatch(rule_id=rule["id"], rule_version=1, state="paused", started_at=1, triggered_at=2,
                                     ended_at=3, trigger_reading_id=original.trigger_reading_id, created=12345))
        db.commit()
    path = "/api/condition-rules/inbox"
    first = client.get(path, params={"review_state": "all", "site": asset["site"]}).json()
    assert len(first["items"]) == 50 and first["total_matching"] == 56 and first["next_cursor"]
    second = client.get(path, params={"review_state": "all", "site": asset["site"], **first["next_cursor"]}).json()
    assert len(second["items"]) == 6 and second["next_cursor"] is None
    assert len({r["id"] for r in first["items"] + second["items"]}) == 56
    assert client.get(path, params={"before_id": match_id}).status_code == 422
    assert client.get(path, params={"review_state": "unknown"}).status_code == 422


def test_inbox_enforces_canonical_site_access_role_and_cursor_scope(client, sign_in):
    asset, rule, match_id = match_fixture(client, sign_in)
    path = "/api/condition-rules/inbox"
    sign_in("planner")
    assert client.get(path).status_code == 403
    with SessionLocal() as db:
        email = uuid.uuid4().hex + "@example.invalid"
        user = User(name="Scoped inbox engineer", email=email, role="engineer", sites=["Habshan Processing Hub"],
                    password_hash=password_hash("Inbox fixture password 2026!"))
        db.add(user); db.flush(); user_id = user.id; db.commit()
    try:
        response = client.post("/api/auth/login", json=dict(email=email, password="Inbox fixture password 2026!"))
        assert response.status_code == 200
        client.headers["X-CSRF-Token"] = response.json()["csrf"]
        result = client.get(path, params={"review_state": "all"}).json()
        assert result["items"] == [] and result["total_matching"] == 0
        assert client.get(path, params={"site": asset["site"]}).status_code == 403
        result = client.get(path, params={"review_state": "all", "before_created": 9999999999, "before_id": match_id}).json()
        assert result["items"] == []
    finally:
        with SessionLocal() as db:
            db.execute(delete(LoginSession).where(LoginSession.user_id == user_id))
            db.execute(delete(SiteMembership).where(SiteMembership.user_id == user_id))
            db.execute(delete(User).where(User.id == user_id)); db.commit()
