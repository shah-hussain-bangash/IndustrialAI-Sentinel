import sqlite3
import uuid

import pytest
from sqlalchemy import select, func

from backend.database import Asset, Audit, Reading, Sensor, SensorEvent, SessionLocal, SnapshotProjection, now
from backend.seed import SITES
from backend.sensors import ensure_sensors
from test_sensor_upgrade import environment, legacy, run


@pytest.fixture
def equipment(client,sign_in):
    sign_in()
    with SessionLocal() as db:
        asset=Asset(tag="FRAME-"+uuid.uuid4().hex[:8],name="Alignment fixture",kind="Pump",site=SITES[0],location="Test bay",criticality="High")
        db.add(asset);db.flush();ensure_sensors(db,[asset]);db.commit()
        return asset.id


def ingest_frame(client,id,overrides=None,omit=()):
    sensors=client.get("/api/sensors",params={"asset_id":id}).json()["items"]
    clock=now()-1
    records=[]
    for sensor in sensors:
        c=sensor["channel"]
        if c in omit:continue
        records.append({"sensor_id":sensor["id"],"message_id":str(uuid.uuid4()),"observed_at":clock,"raw_value":{"vibration":2,"temperature":212,"pressure":500,"flow":2000}[c],"raw_unit":{"vibration":"mm/s","temperature":"degF","pressure":"kPa","flow":"L/min"}[c],"quality":"good","source":"projection-fixture",**(overrides or {}).get(c,{})})
    result=client.post("/api/sensor-events/batches",json={"records":records},headers={"Idempotency-Key":str(uuid.uuid4())})
    assert result.status_code==201,result.text
    return records,result.json()


def preview(client,id):return client.get("/api/snapshot-projections/preview",params={"asset_id":id})


def publish(client,id,frame,key=None):
    return client.post("/api/snapshot-projections",json={"asset_id":id,"preview_signature":frame["preview_signature"]},headers={"Idempotency-Key":key or str(uuid.uuid4())})


def test_projection_reaches_analytics_and_retains_source_events(client,equipment):
    records,receipt=ingest_frame(client,equipment)
    frame=preview(client,equipment).json();assert frame["ready"] and frame["skew_seconds"]==0
    result=publish(client,equipment,frame);assert result.status_code==201,result.text
    payload=result.json();assert payload["values"]=={"vibration":2,"temperature":pytest.approx(100),"pressure":5,"flow":120}
    assert set(payload["event_ids"].values())==set(receipt["event_ids"])
    asset=client.get("/api/assets/"+equipment).json()["asset"]
    assert asset["source"]=="aligned_sensor_events" and asset["reading"]["temperature"]==pytest.approx(100)
    assert asset["health"] is not None
    history=client.get("/api/snapshot-projections/history",params={"asset_id":equipment}).json()["items"]
    assert history[0]["reading_id"]==payload["reading_id"] and history[0]["event_ids"]==payload["event_ids"]
    with SessionLocal() as db:
        assert db.get(SnapshotProjection,payload["reading_id"])
        assert db.scalar(select(Audit).where(Audit.action=="Aligned snapshot published",Audit.details.contains(payload["reading_id"])))
        assert db.scalar(select(func.count()).select_from(SensorEvent).where(SensorEvent.id.in_(receipt["event_ids"])))==4


@pytest.mark.parametrize("case",["missing","suspect","bad","skew","stale","future","newer_snapshot"])
def test_ineligible_frames_never_write_snapshots(client,equipment,case):
    overrides={}
    if case in ("bad","suspect"):overrides={"temperature":{"quality":case}}
    if case=="skew":overrides={"flow":{"observed_at":now()-20}}
    if case=="stale":overrides={c:{"observed_at":now()-2000} for c in ("vibration","temperature","pressure","flow")}
    if case=="future":overrides={"flow":{"observed_at":now()+60}}
    ingest_frame(client,equipment,overrides,omit=("pressure",) if case=="missing" else ())
    if case=="newer_snapshot":
        with SessionLocal() as db:db.add(Reading(asset_id=equipment,timestamp=now(),vibration=2,temperature=70,pressure=5,flow=120));db.commit()
    frame=preview(client,equipment).json();assert not frame["ready"] and frame["reasons"]
    with SessionLocal() as db:before=db.scalar(select(func.count()).select_from(Reading))
    assert publish(client,equipment,frame).status_code==422
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(Reading))==before


def test_uses_oldest_time_without_interpolation(client,equipment):
    anchor=now()-1
    ingest_frame(client,equipment,{"flow":{"observed_at":anchor-4}})
    frame=preview(client,equipment).json();assert frame["ready"]
    result=publish(client,equipment,frame);assert result.status_code==201
    assert result.json()["timestamp"]==anchor-4


def test_latest_bad_event_is_not_silently_replaced_by_older_good(client,equipment):
    ingest_frame(client,equipment,{"temperature":{"observed_at":now()-20}})
    ingest_frame(client,equipment,{"temperature":{"quality":"bad"}})
    frame=preview(client,equipment).json()
    assert not frame["ready"] and any("quality is bad" in r for r in frame["reasons"])


def test_preview_changes_when_new_event_configuration_or_snapshot_arrives(client,equipment):
    ingest_frame(client,equipment);frame=preview(client,equipment).json()
    ingest_frame(client,equipment)
    assert publish(client,equipment,frame).status_code==409
    frame=preview(client,equipment).json()
    with SessionLocal() as db:
        sensor=db.scalar(select(Sensor).where(Sensor.asset_id==equipment));sensor.version+=1;db.commit()
    assert publish(client,equipment,frame).status_code==409
    frame=preview(client,equipment).json()
    with SessionLocal() as db:db.add(Reading(asset_id=equipment,timestamp=now(),vibration=2,temperature=70,pressure=5,flow=120));db.commit()
    assert publish(client,equipment,frame).status_code==409


def test_idempotent_commit_only_creates_one_snapshot(client,equipment):
    ingest_frame(client,equipment);frame=preview(client,equipment).json();key=str(uuid.uuid4())
    first=publish(client,equipment,frame,key);assert first.status_code==201
    assert publish(client,equipment,frame,key).json()==first.json()
    assert publish(client,equipment,frame).status_code==409
    assert not preview(client,equipment).json()["ready"]
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(SnapshotProjection).where(SnapshotProjection.asset_id==equipment))==1


def test_permissions_site_scope_and_csrf(client,equipment,sign_in):
    ingest_frame(client,equipment);frame=preview(client,equipment).json()
    client.headers.pop("X-CSRF-Token");assert publish(client,equipment,frame).status_code==403
    sign_in("technician");assert publish(client,equipment,frame).status_code==403
    sign_in("restricted")
    assert preview(client,equipment).status_code==404
    assert client.get("/api/snapshot-projections/history",params={"asset_id":equipment}).status_code==404
    sign_in();key=str(uuid.uuid4());assert publish(client,equipment,frame,key).status_code==201
    from backend.database import User
    with SessionLocal() as db:
        u=db.scalar(select(User).where(User.email=="engineer@sentinel.local"));sites=u.sites;uid=u.id;u.sites=[SITES[1]];db.commit()
    try:assert publish(client,equipment,frame,key).status_code==404
    finally:
        with SessionLocal() as db:db.get(User,uid).sites=sites;db.commit()


def test_failure_rolls_back_snapshot_provenance_and_asset_version(client,equipment,monkeypatch):
    ingest_frame(client,equipment);frame=preview(client,equipment).json()
    with SessionLocal() as db:version=db.get(Asset,equipment).version
    # Force an audit persistence failure after Reading is flushed.
    from sqlalchemy import event
    def fail(*args):raise RuntimeError("intentional projection audit failure")
    event.listen(Audit,"before_insert",fail)
    try:
        with pytest.raises(RuntimeError):publish(client,equipment,frame)
    finally:event.remove(Audit,"before_insert",fail)
    with SessionLocal() as db:
        assert db.get(Asset,equipment).version==version
        assert not db.scalar(select(Reading).where(Reading.asset_id==equipment))
        assert not db.scalar(select(SnapshotProjection).where(SnapshotProjection.asset_id==equipment))


def test_invalid_stored_conversion_blocks_publication(client,equipment):
    ingest_frame(client,equipment)
    with SessionLocal() as db:
        event=db.scalar(select(SensorEvent).join(Sensor).where(Sensor.asset_id==equipment,Sensor.channel=="temperature"));event.value=99;db.commit()
    frame=preview(client,equipment).json();assert not frame["ready"]
    assert any("does not match" in r for r in frame["reasons"])
    assert publish(client,equipment,frame).status_code==422


def test_revision4_to5_preserves_all_existing_records(tmp_path):
    env,path=environment(tmp_path);legacy(env);run(env,"-m","alembic","upgrade","0004")
    with sqlite3.connect(path) as db:
        sensor=db.execute("SELECT id FROM sensors WHERE channel='temperature'").fetchone()[0]
        db.execute("INSERT INTO sensor_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",("old-event",sensor,"old-message",1.,2.,212.,"degF",100.,"degC","good","fixture","units-v1"))
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'") if r[0]!="alembic_version"]
        before={t:db.execute(f'SELECT * FROM "{t}" ORDER BY 1').fetchall() for t in tables}
    run(env,"scripts/upgrade_database.py")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0]=="0019"
        for t,rows in before.items():assert db.execute(f'SELECT * FROM "{t}" ORDER BY 1').fetchall()==rows
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
    run(env,"-m","alembic","check")
