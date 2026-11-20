import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import uuid

import pytest
from sqlalchemy import select,func,event

from backend.database import Audit,Idempotency,Sensor,SensorEvent,SessionLocal,TelemetryGateway,User,now
from backend.seed import SITES
from test_projections import equipment
from test_sensor_upgrade import environment,legacy,run


def key():return {"Idempotency-Key":str(uuid.uuid4())}


def create(client,id,request_key=None,**changes):
    return client.post("/api/gateways",json={"asset_id":id,"name":"Scoped fixture","lifetime_days":7,**changes},headers={"Idempotency-Key":request_key or str(uuid.uuid4())})


def lifecycle(client,credential,action,request_key=None,**changes):
    body={"expected_version":credential["gateway"]["version"],**({"lifetime_days":7} if action=="rotate" else {}),**changes}
    return client.post(f"/api/gateways/{credential['gateway']['id']}/{action}",json=body,headers={"Idempotency-Key":request_key or str(uuid.uuid4())})


def records(client,id):
    sensors=client.get("/api/sensors",params={"asset_id":id}).json()["items"];clock=now()-1
    return [{"sensor_id":s["id"],"message_id":str(uuid.uuid4()),"observed_at":clock,"raw_value":{"temperature":70,"vibration":2,"pressure":5,"flow":120}[s["channel"]],"raw_unit":s["unit"],"quality":"good"} for s in sensors]


def send(client,credential,rows,request_key=None):
    return client.post("/api/gateway-events/batches",json={"records":rows},headers={"Authorization":"Bearer "+credential,"Idempotency-Key":request_key or str(uuid.uuid4())})


def identity(client,token):return client.get("/api/gateway-identity",headers={"Authorization":"Bearer "+token})


def test_asset_scoped_credential_sends_without_browser_session_and_stores_no_secret(client,equipment,sign_in):
    rows=records(client,equipment);sign_in("admin");request_key=str(uuid.uuid4())
    first=create(client,equipment,request_key);assert first.status_code==201
    issued=first.json();token=issued["credential"];id=issued["gateway"]["id"]
    assert create(client,equipment,request_key).json()["credential"] is None
    assert len(client.get("/api/gateways").json()["items"])>=1
    client.cookies.clear()
    assert identity(client,token).json()["asset_id"]==equipment
    k=str(uuid.uuid4());result=send(client,token,rows,k);assert result.status_code==201
    assert result.json()["inserted"]==4 and result.json()["snapshot_projection"] is False
    assert send(client,token,rows,k).json()==result.json()
    assert send(client,token,rows).json()["duplicates"]==4
    assert client.get("/api/documents",headers={"Authorization":"Bearer "+token}).status_code==401
    assert client.get("/api/gateways",headers={"Authorization":"Bearer "+token}).status_code==401
    with SessionLocal() as db:
        gateway=db.get(TelemetryGateway,id)
        assert gateway.token_hash==hashlib.sha256(token.encode()).hexdigest()
        assert gateway.accepted_batches==2 and gateway.last_used is not None
        assert set(db.scalars(select(SensorEvent.source).join(Sensor).where(Sensor.asset_id==equipment)))=={"gateway:"+id}
        saved=json.dumps(list(db.scalars(select(Idempotency.response))))+" ".join(db.scalars(select(Audit.details)))
        assert token not in saved and token.split(".")[-1] not in saved
        assert db.scalar(select(Audit).where(Audit.action=="Gateway batch accepted",Audit.details.contains(id)))


def test_rotation_and_revocation_invalidate_old_credentials_and_keep_event_dedup(client,equipment,sign_in):
    rows=records(client,equipment);sign_in("admin");issued=create(client,equipment).json();old=issued["credential"]
    assert send(client,old,rows).status_code==201
    k=str(uuid.uuid4());rotated=lifecycle(client,issued,"rotate",k);assert rotated.status_code==200
    fresh=rotated.json();new=fresh["credential"];assert new!=old
    assert lifecycle(client,issued,"rotate",k).json()["credential"] is None
    assert identity(client,old).status_code==401
    assert send(client,new,rows).json()["duplicates"]==4
    assert lifecycle(client,issued,"rotate").status_code==409
    revoked=lifecycle(client,fresh,"revoke");assert revoked.status_code==200
    assert revoked.json()["gateway"]["status"]=="revoked"
    assert identity(client,new).status_code==401 and send(client,new,rows).status_code==401
    assert lifecycle(client,fresh,"rotate").status_code==409


def test_scope_and_batch_atomicity_fail_without_metrics_or_event_writes(client,equipment,sign_in):
    rows=records(client,equipment)
    other=next(s["id"] for s in client.get("/api/sensors").json()["items"] if s["asset_id"]!=equipment)
    sign_in("admin");issued=create(client,equipment).json();token=issued["credential"]
    assert send(client,token,[{**rows[0],"sensor_id":other}]).status_code==404
    bad=[rows[0],{**rows[1],"raw_unit":"wrong-unit"}]
    assert send(client,token,bad).status_code==422
    assert send(client,token,[{**rows[0],"source":"fake-source"}]).status_code==422
    with SessionLocal() as db:
        assert not db.scalar(select(SensorEvent).where(SensorEvent.sensor_id==rows[0]["sensor_id"]))
        assert db.get(TelemetryGateway,issued["gateway"]["id"]).accepted_batches==0
    assert send(client,token,[]).status_code==422
    assert send(client,token,[rows[0]]*501).status_code==422


def test_expiry_role_and_issuer_site_loss_block_gateway(client,equipment,sign_in):
    sign_in("admin");issued=create(client,equipment).json();token=issued["credential"]
    with SessionLocal() as db:
        admin=db.scalar(select(User).where(User.email=="admin@sentinel.local"));uid=admin.id;sites=admin.sites;admin.sites=[SITES[1]];db.commit()
    try:assert identity(client,token).status_code==401
    finally:
        with SessionLocal() as db:db.get(User,uid).sites=sites;db.commit()
    with SessionLocal() as db:db.get(User,uid).role="engineer";db.commit()
    try:assert identity(client,token).status_code==401
    finally:
        with SessionLocal() as db:db.get(User,uid).role="admin";db.commit()
    with SessionLocal() as db:
        g=db.get(TelemetryGateway,issued["gateway"]["id"]);g.created=now()-86400;g.expires=now()-1;db.commit()
    assert identity(client,token).status_code==401
    assert next(g for g in client.get("/api/gateways").json()["items"] if g["id"]==issued["gateway"]["id"])["status"]=="expired"


def test_management_requires_admin_csrf_and_site_scope(client,equipment,sign_in):
    assert create(client,equipment).status_code==403
    sign_in("admin");client.headers.pop("X-CSRF-Token");assert create(client,equipment).status_code==403
    sign_in("admin")
    with SessionLocal() as db:
        u=db.scalar(select(User).where(User.email=="admin@sentinel.local"));sites=u.sites;uid=u.id;u.sites=[SITES[1]];db.commit()
    try:assert create(client,equipment).status_code==404
    finally:
        with SessionLocal() as db:db.get(User,uid).sites=sites;db.commit()
    assert create(client,equipment,name=" ").status_code==422
    assert create(client,equipment,lifetime_days=91).status_code==422
    assert create(client,equipment,scope="all-assets").status_code==422


def test_invalid_credentials_and_revoked_receipt_replays_fail(client,equipment,sign_in):
    rows=records(client,equipment);sign_in("admin");issued=create(client,equipment).json();token=issued["credential"];k=str(uuid.uuid4())
    assert send(client,token,rows,k).status_code==201
    assert send(client,token,[{**rows[0],"raw_value":1}],k).status_code==409
    assert lifecycle(client,issued,"revoke").status_code==200
    assert send(client,token,rows,k).status_code==401
    for credential in ("",token+"x","sgw."+str(uuid.uuid4())+"."+"x"*43):assert identity(client,credential).status_code==401


def test_gateway_ingest_rollback_includes_metrics_and_audit(client,equipment,sign_in):
    rows=records(client,equipment);sign_in("admin");issued=create(client,equipment).json()
    def fail(mapper,connection,target):
        if target.action=="Gateway batch accepted":raise RuntimeError("intentional gateway audit failure")
    event.listen(Audit,"before_insert",fail)
    try:
        with pytest.raises(RuntimeError):send(client,issued["credential"],rows)
    finally:event.remove(Audit,"before_insert",fail)
    with SessionLocal() as db:
        g=db.get(TelemetryGateway,issued["gateway"]["id"]);assert g.accepted_batches==0 and g.last_used is None
        assert not db.scalar(select(SensorEvent).where(SensorEvent.sensor_id==rows[0]["sensor_id"]))


def test_sender_validates_transport_without_transmitting_credential():
    path=Path(__file__).resolve().parents[1]/"scripts/send_gateway_sample.py"
    spec=importlib.util.spec_from_file_location("sample_sender",path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module.base_url("http://127.0.0.1:8127/")=="http://127.0.0.1:8127"
    assert module.base_url("https://example.test")=="https://example.test"
    for value in ("http://example.test","file:///private","https://user:secret@example.test","http://localhost:8127/?secret=x","https://example.test/redirect"):
        with pytest.raises(ValueError):module.base_url(value)


def test_revision7_to8_preserves_existing_rows_and_creates_no_credentials(tmp_path):
    env,path=environment(tmp_path);legacy(env);run(env,"-m","alembic","upgrade","0007")
    with sqlite3.connect(path) as db:
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'") if r[0]!="alembic_version"]
        before={t:db.execute(f'SELECT * FROM "{t}" ORDER BY 1').fetchall() for t in tables}
    run(env,"scripts/upgrade_database.py")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0]=="0008"
        for t,rows in before.items():assert db.execute(f'SELECT * FROM "{t}" ORDER BY 1').fetchall()==rows
        assert db.execute("SELECT count(*) FROM telemetry_gateways").fetchone()[0]==0
    run(env,"-m","alembic","check")
