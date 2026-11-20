"""Bounded, atomic sensor ingestion. No unsynchronized snapshot projection."""
from typing import Literal
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import Audit, Sensor, SensorEvent, User, now
from .security import allow, current_user, get_db

# canonical = raw * scale + offset; pressure uses the international psi.
UNITS = {
    "vibration": {"mm/s": (1, 0), "in/s": (25.4, 0), "m/s": (1000, 0)},
    "temperature": {"degC": (1, 0), "degF": (5/9, -32*5/9), "K": (1, -273.15)},
    "pressure": {"bar": (1, 0), "kPa": (.01, 0), "MPa": (10, 0), "psi": (.06894757293168, 0)},
    "flow": {"m3/h": (1, 0), "L/min": (.06, 0), "m3/s": (3600, 0), "L/s": (3.6, 0)},
}
BOUNDS = {"vibration": (0, 200), "temperature": (-100, 500), "pressure": (0, 1000), "flow": (0, 100000)}


def convert(channel, unit, value):
    if unit not in UNITS[channel]:
        raise HTTPException(422, f"Unsupported {channel} unit: {unit}.")
    scale, offset = UNITS[channel][unit]
    result = value * scale + offset
    low, high = BOUNDS[channel]
    if not low <= result <= high:
        raise HTTPException(422, f"Converted {channel} must be within {low} to {high} in its canonical unit.")
    return result


class EventInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    sensor_id: str = Field(min_length=1, max_length=36)
    message_id: str = Field(min_length=1, max_length=100)
    observed_at: FiniteFloat = Field(gt=0)
    raw_value: FiniteFloat
    raw_unit: str = Field(min_length=1, max_length=20)
    quality: Literal["good", "suspect", "bad"] = "good"
    source: str = Field(default="manual", min_length=1, max_length=80)


class EventBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    records: list[EventInput] = Field(min_length=1, max_length=500)


def serialize(event):
    return {key: getattr(event, key) for key in ("id", "sensor_id", "message_id", "observed_at", "received_at", "raw_value", "raw_unit", "value", "unit", "quality", "source", "conversion")}



def store_event(db, record, sensor, asset, user, received):
    insert = sqlite_insert if db.bind.dialect.name == "sqlite" else postgres_insert
    if record.observed_at > received + 120:
        raise HTTPException(422, "Event timestamp is more than 120 seconds in the future.")
    canonical = convert(sensor.channel, record.raw_unit, record.raw_value)
    values = record.model_dump()
    values.update(id=str(uuid.uuid4()), received_at=received, value=canonical, unit=sensor.unit, conversion="units-v1")
    inserted_id = db.execute(insert(SensorEvent).values(**values).on_conflict_do_nothing(index_elements=["sensor_id", "message_id"]).returning(SensorEvent.id)).scalar_one_or_none()
    event = db.scalar(select(SensorEvent).where(SensorEvent.sensor_id == sensor.id, SensorEvent.message_id == record.message_id))
    if any(getattr(event, k) != v for k, v in record.model_dump().items()):
        raise HTTPException(409, "Message ID already exists with different content. No events in this batch were saved.")
    if inserted_id is not None:
        db.add(Audit(site=asset.site, actor=user.name, action="Sensor event ingested", target=f"{asset.tag}/{sensor.channel}", details=f"Event {event.id}; message {event.message_id}; {event.raw_value} {event.raw_unit} -> {event.value} {event.unit}; units-v1; source {event.source}; quality {event.quality}."))
    return event, inserted_id is not None

def create_event_router(asset_for, idempotent, finish):
    router = APIRouter(prefix="/api/sensor-events", tags=["Sensor events"])

    def authorized_sensor(db, user, id):
        sensor = db.get(Sensor, id)
        if not sensor:
            raise HTTPException(404, "Sensor not found.")
        asset = asset_for(db, user, sensor.asset_id)
        return sensor, asset

    @router.get("")
    def history(sensor_id: str, limit: int = Query(50, ge=1, le=200), user: User = Depends(current_user), db: Session = Depends(get_db)):
        sensor, _ = authorized_sensor(db, user, sensor_id)
        rows = db.scalars(select(SensorEvent).where(SensorEvent.sensor_id == sensor_id).order_by(SensorEvent.observed_at.desc(), SensorEvent.received_at.desc(), SensorEvent.id.desc()).limit(limit)).all()
        return {"items": [serialize(r) for r in rows], "supported_units": list(UNITS[sensor.channel]), "canonical_unit": sensor.unit, "bounds": BOUNDS[sensor.channel], "limit": limit, "scope": "Independent events only. Equipment analytics still use complete snapshots."}

    @router.post("/batches", status_code=201)
    def ingest(body: EventBatch, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
        allow(user, "engineer", "admin")
        # Recheck current site permissions even for an idempotency replay.
        prepared = []
        received = now()
        for record in body.records:
            sensor, asset = authorized_sensor(db, user, record.sensor_id)
            prepared.append((record, sensor, asset))
        key, digest, old = idempotent(db, request, user, body.model_dump())
        if old is not None:
            return old
        inserted, duplicates, ids = 0, 0, []
        try:
            for record, sensor, asset in prepared:
                event, was_inserted = store_event(db, record, sensor, asset, user, received)
                inserted += int(was_inserted)
                duplicates += int(not was_inserted)
                ids.append(event.id)
            response = {"inserted": inserted, "duplicates": duplicates, "event_ids": ids, "snapshot_projection": False}
            return finish(db, key, digest, response)
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Concurrent ingestion conflicted. Retry with the same idempotency key.")
        except Exception:
            db.rollback()
            raise

    return router
