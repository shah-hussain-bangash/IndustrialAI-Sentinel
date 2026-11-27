import json
import sqlite3
import uuid

import pytest
from sqlalchemy import select, func, event
from sqlalchemy.exc import IntegrityError

from backend.database import Audit, Sensor, SensorEvent, SensorQuarantine, SessionLocal, now
from backend.seed import SITES
from test_projections import equipment
from test_sensor_upgrade import environment, legacy, run


def sensor_id(client,id):
    return next(r["id"] for r in client.get("/api/sensors",params={"asset_id":id}).json()["items"] if r["channel"]=="temperature")


def payload(**changes):
    return {"message_id":str(uuid.uuid4()),"observed_at":now()-2,"raw_value":212,"raw_unit":"wrong-unit","quality":"good","source":"review-fixture",**changes}


def intake(client,id,raw,key=None):
    return client.post("/api/sensor-intake/"+id,json={"raw_payload":raw},headers={"Idempotency-Key":key or str(uuid.uuid4())})


def resolve(client,item,action="replay",key=None,**changes):
    body={"expected_version":item["version"],"reason":"Verified the intended Fahrenheit unit in this test."}
    if action=="replay":body.update(raw_value=212,raw_unit="degF",observed_at=item["raw_payload"].get("observed_at",now()-1),quality="good")
    return client.post(f"/api/sensor-quarantine/{item['id']}/{action}",json={**body,**changes},headers={"Idempotency-Key":key or str(uuid.uuid4())})


def queue(client,id,status="all"):
    return client.get("/api/sensor-quarantine",params={"sensor_id":id,"status":status})


def test_rejected_payload_is_preserved_deduplicated_and_replayed(client,equipment):
    sensor=sensor_id(client,equipment);raw=payload();key=str(uuid.uuid4())
    first=intake(client,sensor,raw,key);assert first.status_code==201,first.text
    item=first.json()["item"];assert item["status"]=="pending" and item["raw_payload"]==raw and item["validation_errors"]
    assert intake(client,sensor,raw,key).json()==first.json()
    assert intake(client,sensor,raw).json()["duplicate"] is True
    with SessionLocal() as db:assert not db.scalar(select(SensorEvent).where(SensorEvent.sensor_id==sensor))
    replay_key=str(uuid.uuid4());result=resolve(client,item,key=replay_key);assert result.status_code==200,result.text
    assert resolve(client,item,key=replay_key).json()==result.json()
    assert result.json()["snapshot_projection"] is False
    row=queue(client,sensor).json()["items"][0]
    assert row["raw_payload"]==raw and row["validation_errors"]==item["validation_errors"]
    assert row["version"]==2 and row["status"]=="replayed" and row["review_reason"]
    assert row["corrected_payload"]["raw_unit"]=="degF"
    with SessionLocal() as db:
        e=db.get(SensorEvent,result.json()["event_id"])
        assert e.value==pytest.approx(100) and e.raw_value==212 and e.source=="quarantine-review"
        assert e.message_id=="quarantine:"+item["id"] and row["corrected_event_id"]==e.id
        assert db.scalar(select(Audit).where(Audit.action=="Quarantined payload corrected and replayed",Audit.details.contains(e.id)))
        assert db.scalar(select(func.count()).select_from(SensorEvent).where(SensorEvent.sensor_id==sensor))==1
    assert resolve(client,item).status_code==409
    assert resolve(client,item,"dismiss").status_code==409
    assert queue(client,sensor,"pending").json()["items"]==[]


def test_valid_intake_uses_normal_event_deduplication(client,equipment):
    id=sensor_id(client,equipment);raw=payload(raw_unit="degF")
    result=intake(client,id,raw);assert result.status_code==201 and result.json()["outcome"]=="accepted"
    assert intake(client,id,raw).json()["duplicate"] is True
    conflict=intake(client,id,{**raw,"raw_value":200})
    assert conflict.status_code==201 and conflict.json()["outcome"]=="quarantined"
    corrected=resolve(client,conflict.json()["item"],raw_value=200)
    assert corrected.status_code==200
    with SessionLocal() as db:
        original=db.get(SensorEvent,result.json()["event_id"])
        assert original.raw_value==212
        assert db.get(SensorEvent,corrected.json()["event_id"]).raw_value==200


@pytest.mark.parametrize("changes",[{"raw_value":"NaN"},{"raw_value":"Infinity"},{"raw_unit":"psi"},{"observed_at":-1},{"observed_at":1e20},{"quality":"unknown"},{"unexpected":"field"},{"message_id":""},{"raw_value":1000000,"raw_unit":"degC"}])
def test_rejection_reasons_are_retained_without_sensor_events(client,equipment,changes):
    id=sensor_id(client,equipment);raw=payload(**changes)
    response=intake(client,id,raw);assert response.status_code==201,response.text
    item=response.json()["item"];assert item["raw_payload"]==raw and item["validation_errors"]
    with SessionLocal() as db:assert not db.scalar(select(SensorEvent).where(SensorEvent.sensor_id==id))


def test_dismiss_keeps_evidence_and_is_idempotent(client,equipment):
    id=sensor_id(client,equipment);item=intake(client,id,payload()).json()["item"];key=str(uuid.uuid4())
    result=resolve(client,item,"dismiss",key);assert result.status_code==200
    assert resolve(client,item,"dismiss",key).json()==result.json()
    row=queue(client,id).json()["items"][0]
    assert row["status"]=="dismissed" and row["raw_payload"]==item["raw_payload"] and row["corrected_event_id"] is None
    assert resolve(client,item).status_code==409
    with SessionLocal() as db:assert not db.scalar(select(SensorEvent).where(SensorEvent.sensor_id==id))


def test_invalid_correction_preserves_pending_state(client,equipment):
    id=sensor_id(client,equipment);item=intake(client,id,payload()).json()["item"]
    for changes in ({"raw_unit":"psi"},{"observed_at":now()+1000},{"raw_value":"NaN"},{"reason":"short"},{"reason":"          "},{"unexpected":"x"}):
        assert resolve(client,item,**changes).status_code==422
    assert resolve(client,item,expected_version=2).status_code==409
    row=queue(client,id).json()["items"][0];assert row["version"]==1 and row["status"]=="pending"
    with SessionLocal() as db:assert not db.scalar(select(SensorEvent).where(SensorEvent.sensor_id==id))


def test_intake_limits_binding_and_unsafe_json(client,equipment):
    id=sensor_id(client,equipment)
    for raw in (payload(extra="x"*5000),{str(i):i for i in range(17)},payload(sensor_id="wrong"),payload(extra={"a":{"b":{"c":{"d":{"e":{"f":{"g":"deep"}}}}}}})):
        assert intake(client,id,raw).status_code==422
    bad_json='{"raw_payload":{"raw_value":NaN}}'
    response=client.post("/api/sensor-intake/"+id,content=bad_json,headers={"Content-Type":"application/json","Idempotency-Key":str(uuid.uuid4())})
    assert response.status_code==422
    assert queue(client,id).json()["items"]==[]
    assert client.get("/api/sensor-quarantine",params={"sensor_id":id,"limit":101}).status_code==422


def test_roles_csrf_site_scope_and_replay_scope(client,equipment,sign_in):
    id=sensor_id(client,equipment);item=intake(client,id,payload()).json()["item"]
    client.headers.pop("X-CSRF-Token");assert resolve(client,item).status_code==403
    assert intake(client,id,payload()).status_code==403
    sign_in("technician");assert resolve(client,item).status_code==403 and intake(client,id,payload()).status_code==403
    assert queue(client,id).status_code==200
    sign_in("restricted");assert queue(client,id).status_code==404 and intake(client,id,payload()).status_code==403
    assert resolve(client,item).status_code==403
    sign_in();key=str(uuid.uuid4());assert resolve(client,item,key=key).status_code==200
    from backend.database import User
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email=="engineer@sentinel.local"));uid=user.id;sites=user.sites;user.sites=[SITES[1]];db.commit()
    try:
        assert resolve(client,item,key=key).status_code==404
        assert intake(client,id,payload()).status_code==404
        assert queue(client,id).status_code==404
    finally:
        with SessionLocal() as db:db.get(User,uid).sites=sites;db.commit()


def test_resolution_rollback_includes_event_status_and_audit(client,equipment):
    id=sensor_id(client,equipment);item=intake(client,id,payload()).json()["item"]
    def fail(mapper,connection,target):
        if target.action=="Quarantined payload corrected and replayed":raise RuntimeError("intentional review audit failure")
    event.listen(Audit,"before_insert",fail)
    try:
        with pytest.raises(RuntimeError):resolve(client,item)
    finally:event.remove(Audit,"before_insert",fail)
    row=queue(client,id).json()["items"][0];assert row["status"]=="pending" and row["version"]==1
    with SessionLocal() as db:assert not db.scalar(select(SensorEvent).where(SensorEvent.sensor_id==id))


def test_database_constraints_protect_resolution(client,equipment):
    id=sensor_id(client,equipment);item=intake(client,id,payload()).json()["item"]
    for changes in ({"status":"invalid"},{"status":"replayed"},{"status":"dismissed"},{"version":0}):
        with SessionLocal() as db:
            row=db.get(SensorQuarantine,item["id"])
            for k,v in changes.items():setattr(row,k,v)
            with pytest.raises(IntegrityError):db.commit()


def test_revision5_to6_preserves_existing_tables(tmp_path):
    env,path=environment(tmp_path);legacy(env);run(env,"-m","alembic","upgrade","0005")
    with sqlite3.connect(path) as db:
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'") if r[0]!="alembic_version"]
        before={t:db.execute(f'SELECT * FROM "{t}" ORDER BY 1').fetchall() for t in tables}
    run(env,"scripts/upgrade_database.py")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0]=="0018"
        for t,rows in before.items():assert db.execute(f'SELECT * FROM "{t}" ORDER BY 1').fetchall()==rows
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
    run(env,"-m","alembic","check")
