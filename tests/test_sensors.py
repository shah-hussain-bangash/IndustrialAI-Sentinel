import uuid

import pytest
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from backend.database import Asset, Audit, Reading, Sensor, SessionLocal, now
from backend.seed import SITES
from backend.sensors import ensure_sensors, CHANNELS


def test_registry_auth_and_site_boundaries(client, sign_in):
    assert client.get("/api/sensors").status_code == 401
    sign_in("restricted")
    result = client.get("/api/sensors").json()
    assert result["items"] and all(s["site"] == SITES[1] for s in result["items"])
    assert client.get("/api/sensors", params={"site":SITES[0]}).status_code == 404
    with SessionLocal() as db:
        foreign = db.scalar(select(Sensor).join(Asset).where(Asset.site == SITES[0]))
        foreign_id, foreign_asset = foreign.id, foreign.asset_id
    assert client.get("/api/sensors", params={"asset_id":foreign_asset}).status_code == 404
    sign_in("engineer")
    # Enforce site isolation independently of role by narrowing this session user's sites.
    from backend.database import User
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == "engineer@sentinel.local"))
        old_sites = u.sites
        u.sites = [SITES[1]]
        db.commit()
    try:
        assert client.patch("/api/sensors/"+foreign_id,json={"expected_version":1,"label":"Blocked","expected_interval_seconds":300,"stale_after_seconds":900}).status_code == 404
    finally:
        with SessionLocal() as db:
            db.get(User,u.id).sites = old_sites
            db.commit()


def test_identities_are_stable_and_backfill_preserves_configuration(client, sign_in):
    sign_in()
    first = client.get("/api/sensors").json()["items"]
    assert first
    row = first[0]
    expected = str(uuid.uuid5(uuid.NAMESPACE_URL,f"industrialai-sentinel/sensor/{row['asset_id']}/{row['channel']}"))
    assert row["id"] == expected and CHANNELS[row["channel"]] == row["unit"]
    body = {"expected_version":row["version"],"label":"Configured test channel","expected_interval_seconds":60,"stale_after_seconds":180}
    assert client.patch("/api/sensors/"+row["id"],json=body).status_code == 200
    with SessionLocal() as db:
        ensure_sensors(db,list(db.scalars(select(Asset))))
        ensure_sensors(db,list(db.scalars(select(Asset))))
        db.commit()
    second = client.get("/api/sensors").json()["items"]
    changed = next(s for s in second if s["id"] == row["id"])
    assert len(second) == len(first)
    assert changed["label"] == body["label"] and changed["expected_interval_seconds"] == 60


def test_new_asset_creates_four_mapped_sensors_atomically(client, sign_in):
    sign_in()
    key = str(uuid.uuid4())
    headers={"Idempotency-Key":key}
    body={"tag":"SNS-"+key[:8],"name":"Sensor fixture equipment","kind":"Pump","site":SITES[0],"location":"Test bay","criticality":"High"}
    first=client.post("/api/assets",json=body,headers=headers)
    second=client.post("/api/assets",json=body,headers=headers)
    assert first.status_code == second.status_code == 201
    sensors=client.get("/api/sensors",params={"asset_id":first.json()["id"]}).json()
    assert sensors["summary"]["sensors"] == sensors["summary"]["missing"] == 4
    assert {s["channel"]:s["unit"] for s in sensors["items"]} == CHANNELS
    assert first.json()["sensor_count"] == 4


def test_configuration_permissions_version_validation_and_audit(client,sign_in):
    sign_in()
    row=client.get("/api/sensors").json()["items"][1]
    body={"expected_version":row["version"],"label":"Inspection channel","expected_interval_seconds":30,"stale_after_seconds":90}
    with SessionLocal() as db:
        count=db.scalar(select(func.count()).select_from(Reading))
    changed=client.patch("/api/sensors/"+row["id"],json=body)
    assert changed.status_code == 200
    assert changed.json()["version"] == row["version"]+1
    assert client.patch("/api/sensors/"+row["id"],json=body).status_code == 409
    invalid={**body,"expected_version":changed.json()["version"],"stale_after_seconds":10}
    assert client.patch("/api/sensors/"+row["id"],json=invalid).status_code == 422
    assert client.patch("/api/sensors/"+row["id"],json={**body,"unit":"changed"}).status_code == 422
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Reading)) == count
        assert db.scalar(select(Audit).where(Audit.action=="Sensor configuration changed",Audit.target.like('%/'+row["channel"])))
    sign_in("technician")
    assert client.patch("/api/sensors/"+row["id"],json=body).status_code == 403
    sign_in()
    client.headers.pop("X-CSRF-Token")
    assert client.patch("/api/sensors/"+row["id"],json=body).status_code == 403


def test_quality_and_freshness_are_independent(client,sign_in):
    sign_in()
    with SessionLocal() as db:
        a=Asset(tag="QUAL-"+uuid.uuid4().hex[:8],name="Quality fixture",kind="Pump",site=SITES[0],location="Test",criticality="Low")
        db.add(a);db.flush();ensure_sensors(db,[a]);db.add(Reading(asset_id=a.id,timestamp=now()-1800,vibration=2,temperature=70,pressure=5,flow=100,quality="good"));db.commit();id=a.id
    rows=client.get("/api/sensors",params={"asset_id":id}).json()
    assert rows["summary"]["stale"] == 4 and rows["summary"]["fresh_good"] == 0
    assert all(s["quality"]=="good" and s["freshness"]=="stale" for s in rows["items"])
    with SessionLocal() as db:
        r=db.scalar(select(Reading).where(Reading.asset_id==id));r.timestamp=now();r.quality="bad";db.commit()
    rows=client.get("/api/sensors",params={"asset_id":id}).json()
    assert rows["summary"]["quality_review"] == 4
    assert all(s["freshness"]=="fresh" and s["status"]=="warning" for s in rows["items"])


def test_registry_database_constraints(client):
    with SessionLocal() as db:
        row=db.scalar(select(Sensor))
        values={"id":str(uuid.uuid4()),"asset_id":row.asset_id,"channel":row.channel,"unit":row.unit,"label":"Invalid","expected_interval_seconds":300,"stale_after_seconds":900,"version":1,"created":now()}
    for overrides in ({}, {"asset_id":"nonexistent"}, {"channel":"unsupported","unit":"x"}):
        with SessionLocal() as db:
            db.add(Sensor(**{**values,**overrides,"id":str(uuid.uuid4())}))
            with pytest.raises(IntegrityError): db.commit()
