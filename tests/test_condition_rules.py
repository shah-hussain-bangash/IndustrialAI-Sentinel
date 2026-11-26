import uuid
import pytest
from sqlalchemy import select, func, delete
from backend.condition_rules import evaluate
from backend.database import SessionLocal, Asset, Reading, Episode, Audit, User, SiteMembership, LoginSession
from backend.security import password_hash


def samples(values, times=None, qualities=None):
    return [{"timestamp": t, "vibration": v, "quality": q} for t, v, q in
            zip(times or range(0, len(values) * 10, 10), values, qualities or ["good"] * len(values))]


def test_persistence_hysteresis_and_exact_boundaries():
    # A short spike is ignored; the second run triggers, survives the clear band, then clears.
    result = evaluate(samples([6, 4, 6, 6, 6, 4.8, 4.5]), "vibration", 5, .5, 20, 10)
    assert result["trigger_count"] == 1
    assert result["windows"] == [dict(started_at=20, triggered_at=40, ended_at=60, end_reason="cleared")]
    assert not result["active_at_last_sample"]
    assert evaluate(samples([5, 5]), "vibration", 5, 0, 0, 10)["trigger_count"] == 0


@pytest.mark.parametrize("quality", ["bad", "suspect"])
def test_quality_breaks_pending_and_active_runs(quality):
    result = evaluate(samples([6, 6, 6, 6, 6], qualities=["good", "good", quality, "good", "good"]), "vibration", 5, 0, 10, 10)
    assert result["trigger_count"] == 2
    assert result["invalid_samples"] == 1
    assert result["windows"][0]["end_reason"] == "invalid_sample"
    assert result["active_at_last_sample"]


def test_gaps_do_not_count_as_persistence_or_current_alarm():
    result = evaluate(samples([6, 6, 6], times=[1, 1000, 1010]), "vibration", 5, 0, 30, 60)
    assert result["trigger_count"] == 0
    assert result["continuity_breaks"] == 1
    assert result["pending_since"] == 1000
    assert evaluate([], "vibration", 5, 0, 0, 60)["trigger_count"] == 0
    assert evaluate(samples([6]), "vibration", 5, 0, 30, 60)["trigger_count"] == 0


def test_duplicate_times_and_nonfinite_values_break_continuity():
    result = evaluate(samples([6, 6, float("nan"), 6], times=[1, 1, 10, 20]), "vibration", 5, 0, 15, 60)
    assert result["trigger_count"] == 0
    assert result["invalid_samples"] == 1
    assert result["continuity_breaks"] == 1


def body(asset_id):
    return dict(asset_id=asset_id, channel="vibration", threshold=5, hysteresis=.5,
                persistence_seconds=10, maximum_gap_seconds=10)


def test_preview_is_bounded_and_does_not_change_equipment_or_episodes(client, sign_in):
    sign_in("engineer")
    with SessionLocal() as db:
        asset = db.scalar(select(Asset).where(Asset.site == "Ruwais Energy Complex"))
        asset_id, old_threshold = asset.id, asset.threshold
        old_episodes = db.scalar(select(func.count()).select_from(Episode))
        old_audits = db.scalar(select(func.count()).select_from(Audit))
        ids = []
        for i in range(501):
            r = Reading(asset_id=asset_id, timestamp=90000000000 + i * 5, vibration=6,
                        temperature=70, pressure=5, flow=120, quality="good", message_id=str(uuid.uuid4()))
            db.add(r); db.flush(); ids.append(r.id)
        db.commit()
    try:
        response = client.post("/api/condition-rules/preview", json=body(asset_id))
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["preview_only"] and not data["saved"]
        assert data["sample_count"] == 500 and data["history_truncated"]
        assert data["trigger_count"] == 1 and data["active_at_last_sample"]
        with SessionLocal() as db:
            assert db.get(Asset, asset_id).threshold == old_threshold
            assert db.scalar(select(func.count()).select_from(Episode)) == old_episodes
            assert db.scalar(select(func.count()).select_from(Audit)) == old_audits
    finally:
        with SessionLocal() as db:
            db.execute(delete(Reading).where(Reading.id.in_(ids))); db.commit()


def test_preview_role_and_csrf_boundaries(client, sign_in):
    sign_in("planner")
    asset = client.get("/api/assets").json()[0]
    assert client.post("/api/condition-rules/preview", json=body(asset["id"])).status_code == 403
    sign_in("engineer")
    client.headers.pop("X-CSRF-Token", None)
    assert client.post("/api/condition-rules/preview", json=body(asset["id"])).status_code == 403


def test_scoped_engineer_cannot_preview_other_site(client):
    with SessionLocal() as db:
        email = uuid.uuid4().hex + "@example.invalid"
        user = User(name="Scoped rule test", email=email, role="engineer", sites=["Habshan Processing Hub"],
                    password_hash=password_hash("Rule fixture password 2026!"))
        db.add(user); db.flush(); user_id = user.id
        other = db.scalar(select(Asset).where(Asset.site == "Ruwais Energy Complex")).id
        db.commit()
    try:
        response = client.post("/api/auth/login", json=dict(email=email, password="Rule fixture password 2026!"))
        client.headers["X-CSRF-Token"] = response.json()["csrf"]
        assert client.post("/api/condition-rules/preview", json=body(other)).status_code in (403, 404)
    finally:
        with SessionLocal() as db:
            db.execute(delete(LoginSession).where(LoginSession.user_id == user_id))
            db.execute(delete(SiteMembership).where(SiteMembership.user_id == user_id))
            db.execute(delete(User).where(User.id == user_id)); db.commit()


@pytest.mark.parametrize("field,value", [("channel", "unknown"), ("hysteresis", -1), ("persistence_seconds", -1), ("maximum_gap_seconds", 0), ("threshold", 100001)])
def test_invalid_rule_rejected(client, sign_in, field, value):
    sign_in("engineer")
    asset = client.get("/api/assets").json()[0]
    data = body(asset["id"]); data[field] = value
    assert client.post("/api/condition-rules/preview", json=data).status_code == 422
