import csv
import io
import uuid
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, func, select

from backend.database import Asset, Audit, Episode, Reading, SessionLocal, WorkOrder, Investigation, User, now
from backend.reliability import sample_summary
from backend.seed import SITES


@pytest.fixture
def lab_asset(client):
    with SessionLocal() as db:
        a = Asset(tag="LAB-" + uuid.uuid4().hex[:7], name="Laboratory fixture", kind="Pump", site=SITES[0], location="Test", criticality="Critical", threshold=4.5)
        db.add(a)
        db.flush()
        t = now()
        for seconds, vibration in [(600, 1), (300, 2), (10, 3)]:
            db.add(Reading(asset_id=a.id, timestamp=t-seconds, vibration=vibration, temperature=70, pressure=5, flow=100, quality="good"))
        db.commit()
        return a.id


def scenario(client, id):
    a = client.get("/api/assets/"+id).json()
    return {"asset_id": id, "baseline_timestamp": a["readings"][-1]["timestamp"], "baseline_signature":a["readings"][-1]["fingerprint"], "vibration": 8, "temperature": 95, "pressure": 5, "flow": 100}


def test_lab_authentication_and_query_bounds(client, sign_in):
    for path in ("/api/lab/fleet", "/api/lab/export.csv", "/api/lab/scenarios", "/api/lab/compare?ids=x"):
        assert client.get(path).status_code == 401
    sign_in()
    assert client.get("/api/lab/fleet?hours=721").status_code == 422
    assert client.get("/api/lab/fleet?hours=0").status_code == 422
    assert client.get("/api/lab/compare?ids=a&ids=b&ids=c&ids=d").status_code == 422
    assert client.get("/api/lab/compare?ids=a&ids=a").status_code == 422


def test_triage_components_and_quality_window(client, sign_in, lab_asset):
    sign_in()
    investigation_ids = []
    try:
        with SessionLocal() as db:
            creator = db.scalar(select(User).where(User.email == "engineer@sentinel.local"))
            for _ in range(3):
                db.add(Episode(asset_id=lab_asset, title="Fixture episode", severity="warning"))
                inv = Investigation(asset_id=lab_asset, creator_id=creator.id, title="Lab fixture", payload={}, payload_hash="test")
                db.add(inv)
                db.flush()
                investigation_ids.append(inv.id)
                db.add(WorkOrder(reference="LAB-"+uuid.uuid4().hex, asset_id=lab_asset, investigation_id=inv.id, title="Overdue fixture", priority="High", status="planned", due_date="2000-01-01"))
            db.commit()
        result = client.get("/api/lab/fleet?hours=24")
        assert result.status_code == 200
        item = next(i for i in result.json()["items"] if i["asset"]["id"] == lab_asset)
        assert item["components"] == {"criticality":20, "active_episodes":20, "condition":6, "overdue_work":20}
        assert item["score"] == 66 and item["band"] == "Urgent"
        assert item["quality_percent"] == 100 and item["samples"] == 3
        assert not item["needs_data_review"]
        assert "probability" in result.json()["limitation"]
    finally:
        with SessionLocal() as db:
            db.execute(delete(WorkOrder).where(WorkOrder.investigation_id.in_(investigation_ids)))
            db.execute(delete(Investigation).where(Investigation.id.in_(investigation_ids)))
            db.commit()


@pytest.mark.parametrize("quality,age", [("bad", 10), ("good", 7200)])
def test_unknown_condition_is_data_review_not_healthy(client, sign_in, lab_asset, quality, age):
    sign_in()
    with SessionLocal() as db:
        rows = list(db.scalars(select(Reading).where(Reading.asset_id == lab_asset)))
        for i, r in enumerate(sorted(rows, key=lambda r:r.timestamp)):
            r.timestamp = now()-age-(len(rows)-1-i)*300
            r.quality = quality
        db.commit()
    item = next(i for i in client.get("/api/lab/fleet").json()["items"] if i["asset"]["id"] == lab_asset)
    assert item["band"] == "Data review"
    assert item["needs_data_review"]
    assert item["components"]["condition"] == 0


def test_shared_site_isolation_for_all_lab_routes(client, sign_in, lab_asset):
    sign_in("restricted")
    assert all(i["asset"]["site"] == SITES[1] for i in client.get("/api/lab/fleet").json()["items"])
    assert client.get("/api/lab/fleet", params={"site":SITES[0]}).status_code == 404
    assert client.get("/api/lab/compare", params={"ids":lab_asset}).status_code == 404
    assert client.get("/api/lab/scenarios", params={"site":SITES[0]}).status_code == 404
    assert SITES[0] not in client.get("/api/lab/export.csv").text
    body = {"asset_id":lab_asset,"baseline_timestamp":now(),"baseline_signature":"0"*64,"vibration":2,"temperature":70,"pressure":5,"flow":100}
    assert client.post("/api/lab/simulate",json=body).status_code == 404


def test_comparison_statistics_and_constant_sensor_detection(client, sign_in, lab_asset):
    sign_in()
    result = client.get("/api/lab/compare", params={"ids":lab_asset,"hours":24})
    assert result.status_code == 200
    s = result.json()["series"][0]
    assert s["statistics"]["samples"] == 3
    assert s["statistics"]["channels"]["vibration"]["mean"] == 2
    rows = [SimpleNamespace(timestamp=i*3600, quality="good", vibration=i, temperature=70, pressure=5, flow=100) for i in range(12)]
    stats = sample_summary(rows)
    assert stats["channels"]["vibration"]["observed_change_per_hour"] == 1
    assert stats["channels"]["temperature"]["constant_last_12"]
    assert not stats["channels"]["vibration"]["constant_last_12"]
    assert sample_summary([])["channels"]["vibration"]["mean"] is None


def test_scenario_does_not_modify_equipment_or_telemetry(client, sign_in, lab_asset):
    sign_in()
    body = scenario(client,lab_asset)
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(Reading))
        version = db.get(Asset,lab_asset).version
    result = client.post("/api/lab/simulate",json=body)
    assert result.status_code == 200, result.text
    assert result.json()["health_delta"] < 0
    assert result.json()["scenario_condition"]["threshold_exceeded"]
    assert result.json()["baseline"]["vibration"] == 3
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Reading)) == before
        assert db.get(Asset,lab_asset).version == version
    body["baseline_timestamp"] -= 1
    assert client.post("/api/lab/simulate",json=body).status_code == 409


def test_scenario_saving_is_idempotent_and_audited(client, sign_in, lab_asset):
    sign_in()
    body = {**scenario(client,lab_asset),"title":"Pressure and vibration review"}
    headers = {"Idempotency-Key":str(uuid.uuid4())}
    first = client.post("/api/lab/scenarios",json=body,headers=headers)
    repeat = client.post("/api/lab/scenarios",json=body,headers=headers)
    assert first.status_code == repeat.status_code == 201
    assert first.json() == repeat.json()
    assert first.json()["result"]["model_version"]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Audit).where(Audit.id == first.json()["id"])) == 1
    body["title"] = "Changed command"
    assert client.post("/api/lab/scenarios",json=body,headers=headers).status_code == 409
    assert any(h["id"] == first.json()["id"] for h in client.get("/api/lab/scenarios").json())
    sign_in("restricted")
    assert all(h["result"]["site"] != SITES[0] for h in client.get("/api/lab/scenarios").json())


def test_scenario_permissions_csrf_and_input_limits(client, sign_in, lab_asset):
    sign_in()
    body = scenario(client,lab_asset)
    invalid = {**body,"vibration":201}
    assert client.post("/api/lab/simulate",json=invalid).status_code == 422
    client.headers.pop("X-CSRF-Token")
    assert client.post("/api/lab/simulate",json=body).status_code == 403
    sign_in("technician")
    assert client.post("/api/lab/simulate",json=body).status_code == 200
    assert client.post("/api/lab/scenarios",json={**body,"title":"Not authorized"}).status_code == 403


def test_csv_escapes_formula_like_asset_names(client, sign_in, lab_asset):
    sign_in()
    with SessionLocal() as db:
        db.get(Asset,lab_asset).name = "  =HYPERLINK(\"invalid\")"
        db.commit()
    result = client.get("/api/lab/export.csv")
    assert result.status_code == 200
    assert "attachment" in result.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(result.text)))
    assert any(r[1].startswith("'  =") for r in rows[1:])


def test_comparison_is_bounded_and_excludes_bad_values_from_statistics(client, sign_in, lab_asset):
    sign_in()
    with SessionLocal() as db:
        db.execute(delete(Reading).where(Reading.asset_id == lab_asset))
        for i in range(310):
            db.add(Reading(asset_id=lab_asset,timestamp=now()-i,vibration=2,temperature=70,pressure=5,flow=100,quality="good" if i%2 else "bad"))
        db.commit()
    series = client.get("/api/lab/compare",params={"ids":lab_asset}).json()["series"][0]
    assert len(series["readings"]) == 300
    assert series["statistics"]["good_samples"] == 150
    assert series["statistics"]["channels"]["vibration"]["mean"] == 2


def test_scenario_rejects_bad_baseline_and_still_marks_stale_good_baseline(client, sign_in, lab_asset):
    sign_in()
    body = scenario(client,lab_asset)
    with SessionLocal() as db:
        newest = db.scalar(select(Reading).where(Reading.asset_id == lab_asset).order_by(Reading.timestamp.desc()).limit(1))
        newest.quality = "bad"
        db.commit()
    assert client.post("/api/lab/simulate",json=body).status_code == 409
    with SessionLocal() as db:
        for r in db.scalars(select(Reading).where(Reading.asset_id == lab_asset)):
            r.timestamp -= 7200
            r.quality = "good"
        db.commit()
    body = scenario(client,lab_asset)
    result = client.post("/api/lab/simulate",json=body)
    assert result.status_code == 200 and result.json()["baseline_stale"]


def test_baseline_signature_rejects_same_timestamp_value_changes(client, sign_in, lab_asset):
    sign_in()
    body = scenario(client,lab_asset)
    with SessionLocal() as db:
        r = db.scalar(select(Reading).where(Reading.asset_id == lab_asset).order_by(Reading.timestamp.desc()).limit(1))
        r.vibration += 1
        db.commit()
    assert client.post("/api/lab/simulate",json=body).status_code == 409
