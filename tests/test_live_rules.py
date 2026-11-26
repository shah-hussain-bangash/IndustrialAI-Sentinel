import uuid
import pytest
from sqlalchemy import select, func, delete
from backend.database import SessionLocal, ConditionRuleMatch, ConditionRuleDeployment, ConditionRuleRevision, ConditionRule, ConditionRuleReview, ConditionRuleAssignment, ConditionMatchInvestigation, Investigation, RecommendationRevision, WorkOrder, Asset, Reading, Sensor, Episode, Audit, now
from backend.live_rules import process_snapshot


@pytest.fixture(autouse=True)
def cleanup_live_fixture():
    yield
    with SessionLocal() as db:
        assets = list(db.scalars(select(Asset).where(Asset.tag.like("LIVEFIX-%"))))
        for asset in assets:
            ids = list(db.scalars(select(ConditionRule.id).where(ConditionRule.asset_id == asset.id)))
            match_ids = select(ConditionRuleMatch.id).where(ConditionRuleMatch.rule_id.in_(ids))
            investigation_ids = list(db.scalars(select(ConditionMatchInvestigation.investigation_id).where(ConditionMatchInvestigation.match_id.in_(match_ids))))
            db.execute(delete(ConditionMatchInvestigation).where(ConditionMatchInvestigation.match_id.in_(match_ids)))
            for model in (WorkOrder, RecommendationRevision):
                db.execute(delete(model).where(model.investigation_id.in_(investigation_ids)))
            db.execute(delete(Investigation).where(Investigation.id.in_(investigation_ids)))
            db.execute(delete(ConditionRuleAssignment).where(ConditionRuleAssignment.match_id.in_(match_ids)))
            db.execute(delete(ConditionRuleReview).where(ConditionRuleReview.match_id.in_(match_ids)))
            for model in (ConditionRuleMatch, ConditionRuleDeployment, ConditionRuleRevision):
                db.execute(delete(model).where(model.rule_id.in_(ids)))
            db.execute(delete(ConditionRule).where(ConditionRule.asset_id == asset.id))
            for model in (Episode, Reading, Sensor):
                db.execute(delete(model).where(model.asset_id == asset.id))
            db.execute(delete(Audit).where(Audit.target == asset.tag))
            db.delete(asset)
        db.commit()


def call(client, path, body, key=None):
    return client.post(path, json=body, headers={"Idempotency-Key": key or str(uuid.uuid4())})


def draft(client, sign_in, persistence=10):
    sign_in("admin")
    created = call(client, "/api/assets", dict(tag="LIVEFIX-" + uuid.uuid4().hex[:10], name="Live rule fixture", kind="Pump", site="Ruwais Energy Complex", location="Fixture area"))
    assert created.status_code == 201, created.text
    asset = created.json()
    response = call(client, "/api/condition-rules/drafts", dict(asset_id=asset["id"], channel="vibration", threshold=5,
                      hysteresis=.5, persistence_seconds=persistence, maximum_gap_seconds=20,
                      name="Controlled fixture rule", reason="Synthetic fixture"))
    assert response.status_code == 201, response.text
    return asset, response.json()


def control(client, rule, action="activate", version=0, revision=1, key=None):
    return call(client, f"/api/condition-rules/drafts/{rule['id']}/control", dict(action=action, expected_version=version,
                expected_rule_version=revision, reason="Controlled fixture action", confirmed=True), key)


def ingest(client, asset, timestamp, value, quality="good", key=None, message=None):
    return call(client, "/api/telemetry/batches", dict(records=[dict(asset_id=asset["id"], timestamp=timestamp,
                vibration=value, temperature=70, pressure=5, flow=120, quality=quality, message_id=message or str(uuid.uuid4()))]), key)


def matches(rule_id):
    with SessionLocal() as db:
        return [(r.rule_version, r.state) for r in db.scalars(select(ConditionRuleMatch).where(ConditionRuleMatch.rule_id == rule_id).order_by(ConditionRuleMatch.created))]


def test_activation_new_samples_persistence_hysteresis_duplicates_and_pause(client, sign_in):
    asset, rule = draft(client, sign_in)
    result = control(client, rule)
    assert result.status_code == 200, result.text
    start = result.json()["activated_at"] + 1
    assert result.json()["last_evaluated_at"] is None
    assert matches(rule["id"]) == []  # Activation never evaluates existing history.
    assert ingest(client, asset, start, 6).status_code == 200
    assert matches(rule["id"]) == []
    key, message = str(uuid.uuid4()), str(uuid.uuid4())
    assert ingest(client, asset, start + 10, 6, key=key, message=message).status_code == 200
    assert matches(rule["id"]) == [(1, "active")]
    assert ingest(client, asset, start + 10, 6, key=key, message=message).status_code == 200
    assert matches(rule["id"]) == [(1, "active")]
    assert ingest(client, asset, start + 15, 4.8).status_code == 200
    assert matches(rule["id"]) == [(1, "active")]
    assert ingest(client, asset, start + 20, 4.5).status_code == 200
    assert matches(rule["id"]) == [(1, "cleared")]
    assert control(client, rule, "pause", version=1).status_code == 200
    assert ingest(client, asset, start + 30, 6).status_code == 200
    assert ingest(client, asset, start + 40, 6).status_code == 200
    assert matches(rule["id"]) == [(1, "cleared")]
    activity = client.get("/api/condition-rules/activity", params={"asset_id": asset["id"]})
    assert activity.status_code == 200 and any(m["rule_version"] == 1 for m in activity.json()["items"])


def test_exact_revision_is_pinned_and_new_revision_needs_activation(client, sign_in):
    asset, rule = draft(client, sign_in, persistence=0)
    key = str(uuid.uuid4())
    first = control(client, rule, key=key)
    assert control(client, rule, key=key).json() == first.json()
    assert control(client, rule, version=0).status_code == 409
    changed = {**rule["settings"], "threshold": 9, "name": "Revised fixture", "reason": "New draft only", "expected_version": 1}
    assert call(client, f"/api/condition-rules/drafts/{rule['id']}", changed).status_code == 200
    state = client.get(f"/api/condition-rules/drafts/{rule['id']}/deployment").json()
    assert state["rule_version"] == 1 and state["latest_rule_version"] == 2
    assert control(client, rule, version=1, revision=1).status_code == 409
    assert ingest(client, asset, first.json()["activated_at"] + 1, 6).status_code == 200
    assert matches(rule["id"]) == [(1, "active")]
    second = control(client, rule, version=1, revision=2)
    assert second.status_code == 200, second.text
    assert matches(rule["id"]) == [(1, "replaced")]
    assert ingest(client, asset, max(first.json()["activated_at"] + 2, second.json()["activated_at"] + 1), 6).status_code == 200
    assert matches(rule["id"]) == [(1, "replaced")]


@pytest.mark.parametrize("quality,expected", [("bad", "invalid_sample"), ("suspect", "invalid_sample"), ("good", "data_gap")])
def test_quality_and_gaps_interrupt_match_and_restart_persistence(client, sign_in, quality, expected):
    asset, rule = draft(client, sign_in, persistence=0)
    response = control(client, rule); start = response.json()["activated_at"] + 1
    assert ingest(client, asset, start, 6).status_code == 200
    assert ingest(client, asset, start + (25 if quality == "good" else 5), 6, quality).status_code == 200
    result = matches(rule["id"])
    assert result[0] == (1, expected)
    if quality == "good": assert result[-1] == (1, "active")


def test_control_requires_admin_confirmation_csrf_and_current_site(client, sign_in):
    asset, rule = draft(client, sign_in)
    sign_in("engineer")
    assert control(client, rule).status_code == 403
    sign_in("restricted")
    assert client.get(f"/api/condition-rules/drafts/{rule['id']}/deployment").status_code == 403
    sign_in("admin")
    payload = dict(action="activate", expected_version=0, expected_rule_version=1, reason="review", confirmed=False)
    assert call(client, f"/api/condition-rules/drafts/{rule['id']}/control", payload).status_code == 422
    client.headers.pop("X-CSRF-Token", None)
    assert control(client, rule).status_code == 403


def test_out_of_order_history_is_not_replayed_and_transaction_rollback_discards_match(client, sign_in):
    asset, rule = draft(client, sign_in, persistence=0)
    response = control(client, rule); start = response.json()["activated_at"] + 1
    assert ingest(client, asset, start - 100, 9).status_code == 200
    assert matches(rule["id"]) == []
    with SessionLocal() as db:
        row = Reading(asset_id=asset["id"], timestamp=start, vibration=9, temperature=70, pressure=5, flow=120, quality="good")
        db.add(row); process_snapshot(db, db.get(Asset, asset["id"]), row)
        db.rollback()
    assert matches(rule["id"]) == []


def test_first_simulated_snapshot_is_evaluated_and_pause_closes_match(client, sign_in):
    asset, rule = draft(client, sign_in, persistence=0)
    changed = {**rule["settings"], "threshold": 1, "name": "Simulation fixture", "reason": "Low fixture limit", "expected_version": 1}
    response = call(client, f"/api/condition-rules/drafts/{rule['id']}", changed)
    assert response.status_code == 200
    assert control(client, rule, revision=2).status_code == 200
    response = call(client, "/api/simulation/tick", dict(scenario="normal"))
    assert response.status_code == 200, response.text
    assert matches(rule["id"]) == [(2, "active")]
    assert control(client, rule, "pause", version=1, revision=2).status_code == 200
    assert matches(rule["id"]) == [(2, "paused")]
