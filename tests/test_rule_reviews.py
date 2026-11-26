import uuid
from sqlalchemy import select, func
from backend.database import SessionLocal, ConditionRuleReview, ConditionRuleMatch, ConditionRuleDeployment, WorkOrder, Audit
from test_live_rules import cleanup_live_fixture, draft, control, ingest, call


def match_fixture(client, sign_in, paused=True):
    asset, rule = draft(client, sign_in, persistence=0)
    activation = control(client, rule)
    assert activation.status_code == 200
    assert ingest(client, asset, activation.json()["activated_at"] + 1, 7).status_code == 200
    with SessionLocal() as db:
        match_id = db.scalar(select(ConditionRuleMatch.id).where(ConditionRuleMatch.rule_id == rule["id"]))
    assert match_id
    if paused: assert control(client, rule, "pause", version=1).status_code == 200
    return asset, rule, match_id


def review(client, match_id, action="acknowledge", version=0, reason="Simulation review fixture only.", key=None):
    return call(client, f"/api/condition-rules/matches/{match_id}/review", dict(action=action, expected_version=version, reason=reason), key)


def test_review_acknowledge_resolve_idempotency_history_and_no_maintenance_change(client, sign_in):
    asset, rule, match_id = match_fixture(client, sign_in)
    with SessionLocal() as db: orders = db.scalar(select(func.count()).select_from(WorkOrder))
    key = str(uuid.uuid4())
    first = review(client, match_id, key=key)
    assert first.status_code == 200, first.text
    assert first.json()["review"]["state"] == "acknowledged"
    assert review(client, match_id, key=key).json() == first.json()
    assert review(client, match_id, "resolve", version=0).status_code == 409
    second = review(client, match_id, "resolve", version=1, reason="Simulation review completed; no physical work performed.")
    assert second.status_code == 200, second.text
    history = client.get(f"/api/condition-rules/matches/{match_id}/reviews").json()
    assert [r["state"] for r in history["items"]] == ["resolved", "acknowledged"]
    assert [r["version"] for r in history["items"]] == [2, 1]
    assert history["signal_state"] == "paused"
    assert review(client, match_id, version=2).status_code == 409
    activity = client.get("/api/condition-rules/activity", params={"asset_id": asset["id"]}).json()
    assert next(m for m in activity["items"] if m["id"] == match_id)["review"]["state"] == "resolved"
    with SessionLocal() as db:
        assert db.get(ConditionRuleMatch, match_id).state == "paused"
        assert db.get(ConditionRuleDeployment, rule["id"]).state == "paused"
        assert db.scalar(select(func.count()).select_from(WorkOrder)) == orders
        assert db.scalar(select(func.count()).select_from(ConditionRuleReview).where(ConditionRuleReview.match_id == match_id)) == 2
        logs = list(db.scalars(select(Audit).where(Audit.target == asset["tag"], Audit.action.in_(["Rule match acknowledged", "Rule match resolved"]))))
        assert len(logs) == 2


def test_active_match_can_be_acknowledged_but_not_resolved(client, sign_in):
    asset, rule, match_id = match_fixture(client, sign_in, paused=False)
    assert review(client, match_id, "resolve", version=0).status_code == 409
    sign_in("engineer")
    assert review(client, match_id).status_code == 200
    assert review(client, match_id, "resolve", version=1).status_code == 409
    with SessionLocal() as db:
        assert db.get(ConditionRuleMatch, match_id).state == "active"
        assert db.scalar(select(func.count()).select_from(ConditionRuleReview).where(ConditionRuleReview.match_id == match_id)) == 1


def test_review_role_validation_and_csrf_checks(client, sign_in):
    asset, rule, match_id = match_fixture(client, sign_in)
    sign_in("planner")
    assert review(client, match_id).status_code == 403
    assert client.get(f"/api/condition-rules/matches/{match_id}/reviews").status_code == 403
    sign_in("restricted")
    assert review(client, match_id).status_code == 403
    sign_in("admin")
    assert review(client, match_id, reason="    ").status_code == 422
    assert review(client, match_id, reason="Invalid\ncontrol").status_code == 422
    client.headers.pop("X-CSRF-Token", None)
    assert review(client, match_id).status_code == 403
