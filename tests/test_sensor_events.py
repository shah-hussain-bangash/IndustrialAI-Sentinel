import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from backend.database import Asset, Audit, Reading, Sensor, SensorEvent, SessionLocal, now
from backend.seed import SITES
from backend.sensor_events import convert


@pytest.mark.parametrize("channel,unit,raw,expected", [
    ("temperature", "degF", 212, 100), ("temperature", "K", 273.15, 0),
    ("vibration", "in/s", 1, 25.4), ("vibration", "m/s", .001, 1),
    ("pressure", "kPa", 100, 1), ("pressure", "MPa", 1, 10),
    ("pressure", "psi", 1, .06894757293168), ("flow", "L/min", 100, 6),
    ("flow", "m3/s", 1, 3600), ("flow", "L/s", 10, 36),
])
def test_unit_conversions(channel, unit, raw, expected):
    assert convert(channel, unit, raw) == pytest.approx(expected)


@pytest.mark.parametrize("channel,unit,value", [("flow","psi",1), ("pressure","bar",-1), ("temperature","K",0), ("vibration","m/s",1), ("flow","m3/s",1e308)])
def test_conversion_rejects_wrong_dimensions_and_bounds(channel, unit, value):
    with pytest.raises(HTTPException): convert(channel,unit,value)


def record(client, channel="temperature", **changes):
    sensor = next(s for s in client.get("/api/sensors").json()["items"] if s["channel"] == channel)
    return {"sensor_id":sensor["id"], "message_id":str(uuid.uuid4()), "observed_at":now()-2, "raw_value":212, "raw_unit":"degF", "quality":"good", "source":"test-fixture", **changes}


def send(client, records, key=None):
    return client.post("/api/sensor-events/batches", json={"records":records}, headers={"Idempotency-Key":key or str(uuid.uuid4())})


def test_traceability_idempotency_and_snapshot_compatibility(client, sign_in):
    sign_in(); body=record(client);key=str(uuid.uuid4())
    with SessionLocal() as db:
        before=db.scalar(select(func.count()).select_from(Reading))
    first=send(client,[body],key)
    assert first.status_code==201,first.text
    assert first.json()["inserted"]==1 and first.json()["snapshot_projection"] is False
    assert send(client,[body],key).json()==first.json()
    assert send(client,[body]).json()["duplicates"]==1
    assert send(client,[{**body,"raw_value":100}]).status_code==409
    assert send(client,[{**body,"raw_value":100}],key).status_code==409
    result=client.get("/api/sensor-events",params={"sensor_id":body["sensor_id"]}).json()
    event=next(x for x in result["items"] if x["message_id"]==body["message_id"])
    assert event["raw_value"]==212 and event["raw_unit"]=="degF" and event["value"]==pytest.approx(100) and event["unit"]=="degC"
    assert event["conversion"]=="units-v1" and event["received_at"]>=body["observed_at"]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Reading))==before
        assert db.scalar(select(Audit).where(Audit.action=="Sensor event ingested",Audit.details.contains(event["id"])))


def test_batch_atomicity_duplicates_and_out_of_order(client, sign_in):
    sign_in(); first=record(client); bad={**first,"message_id":str(uuid.uuid4()),"raw_unit":"psi"}
    assert send(client,[first,bad]).status_code==422
    with SessionLocal() as db:
        assert db.scalar(select(SensorEvent).where(SensorEvent.message_id==first["message_id"])) is None
    assert send(client,[first,first]).json()["duplicates"]==1
    older={**first,"message_id":str(uuid.uuid4()),"observed_at":first["observed_at"]-1000}
    assert send(client,[older]).status_code==201
    rows=client.get("/api/sensor-events",params={"sensor_id":first["sensor_id"]}).json()["items"]
    assert [r["observed_at"] for r in rows]==sorted([r["observed_at"] for r in rows],reverse=True)
    fresh={**first,"message_id":str(uuid.uuid4())}
    assert send(client,[fresh,{**first,"quality":"bad"}]).status_code==409
    with SessionLocal() as db:assert db.scalar(select(SensorEvent).where(SensorEvent.message_id==fresh["message_id"])) is None


def test_event_validation_roles_csrf_and_limits(client, sign_in):
    assert client.get("/api/sensor-events?sensor_id=x").status_code==401
    sign_in(); r=record(client)
    for overrides in ({"raw_unit":""},{"raw_value":"NaN"},{"raw_value":"Infinity"},{"observed_at":now()+1000},{"observed_at":-1},{"source":" "},{"quality":"unknown"},{"extra":1}):
        assert send(client,[{**r,**overrides}]).status_code==422
    assert send(client,[]).status_code==422
    assert send(client,[r]*501).status_code==422
    assert client.get("/api/sensor-events",params={"sensor_id":r["sensor_id"],"limit":201}).status_code==422
    assert client.get("/api/sensor-events",params={"sensor_id":"missing"}).status_code==404
    assert send(client,[{**r,"sensor_id":"missing"}]).status_code==404
    client.headers.pop("X-CSRF-Token")
    assert send(client,[r]).status_code==403
    sign_in("technician")
    assert send(client,[r]).status_code==403
    assert client.get("/api/sensor-events",params={"sensor_id":r["sensor_id"]}).status_code==200


def test_event_site_boundaries_include_replays(client, sign_in):
    sign_in()
    with SessionLocal() as db:
        sensor=db.scalar(select(Sensor).join(Asset).where(Asset.site==SITES[0],Sensor.channel=="temperature"))
        id=sensor.id
    body=record(client,sensor_id=id);key=str(uuid.uuid4());assert send(client,[body],key).status_code==201
    from backend.database import User
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email=="engineer@sentinel.local"));original=user.sites;uid=user.id;user.sites=[SITES[1]];db.commit()
    try:
        assert send(client,[body],key).status_code==404
        assert client.get("/api/sensor-events",params={"sensor_id":id}).status_code==404
    finally:
        with SessionLocal() as db:db.get(User,uid).sites=original;db.commit()


def test_event_database_constraints(client):
    with SessionLocal() as db:id=db.scalar(select(Sensor.id))
    base=dict(sensor_id=id,message_id=str(uuid.uuid4()),observed_at=now(),raw_value=1,raw_unit="bar",value=1,unit="bar",quality="good",source="test")
    with SessionLocal() as db:db.add(SensorEvent(**base));db.commit()
    for changes in ({},{"sensor_id":"missing"},{"message_id":str(uuid.uuid4()),"quality":"unknown"},{"message_id":str(uuid.uuid4()),"observed_at":-1}):
        with SessionLocal() as db:
            db.add(SensorEvent(**{**base,**changes}))
            with pytest.raises(IntegrityError):db.commit()
