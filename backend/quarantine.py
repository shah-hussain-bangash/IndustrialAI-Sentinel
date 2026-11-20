"""Opt-in bounded intake, rejected-data evidence and controlled human replay."""
import hashlib
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, JsonValue, ValidationError, field_validator
from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from .database import Audit, Sensor, SensorQuarantine, User, now, uid
from .security import allow, current_user, get_db
from .sensor_events import EventInput, UNITS, store_event
from .review_queue import queue_page


class IntakeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    raw_payload: dict[str, JsonValue]

    @field_validator("raw_payload")
    @classmethod
    def bounded_object(cls, value):
        try:
            encoded = json.dumps(value, allow_nan=False, sort_keys=True).encode()
        except (ValueError, TypeError, RecursionError):
            raise ValueError("Use a finite JSON object.")
        if len(encoded) > 4096 or len(value) > 16:
            raise ValueError("Payload must be at most 4096 encoded bytes and 16 fields.")
        def depth(v, level=0):
            if level > 6:
                raise ValueError("Payload nesting exceeds six levels.")
            if isinstance(v, dict):
                for child in v.values(): depth(child, level+1)
            elif isinstance(v, list):
                for child in v: depth(child, level+1)
        depth(value)
        return value


class ReviewReason(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=10, max_length=1000)


class Correction(ReviewReason):
    raw_value: FiniteFloat
    raw_unit: str = Field(min_length=1, max_length=20)
    observed_at: FiniteFloat = Field(gt=0)
    quality: Literal["good", "suspect", "bad"]


def serialize(item):
    return {k: getattr(item, k) for k in ("id", "sensor_id", "raw_payload", "validation_errors", "status", "version", "submitted_by", "created", "corrected_event_id", "corrected_payload", "reviewer_id", "reviewed_at", "review_reason")}


def create_quarantine_router(asset_for, idempotent, finish):
    router = APIRouter(tags=["Sensor data review"])

    def scoped_sensor(db, user, id):
        sensor = db.get(Sensor, id)
        if not sensor: raise HTTPException(404, "Sensor not found.")
        return sensor, asset_for(db, user, sensor.asset_id)

    def scoped_item(db, user, id):
        item = db.get(SensorQuarantine, id)
        if not item: raise HTTPException(404, "Review item not found.")
        sensor, asset = scoped_sensor(db, user, item.sensor_id)
        return item, sensor, asset

    @router.post("/api/sensor-intake/{sensor_id}", status_code=201)
    def intake(sensor_id: str, body: IntakeInput, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
        allow(user, "engineer", "admin")
        sensor, asset = scoped_sensor(db, user, sensor_id)
        if "sensor_id" in body.raw_payload and body.raw_payload["sensor_id"] != sensor_id:
            raise HTTPException(422, "Payload sensor_id must match the intake sensor. No data was retained.")
        key, hashed, old = idempotent(db, request, user, body.model_dump())
        if old is not None: return old
        try:
            errors = []
            try:
                record = EventInput.model_validate({**body.raw_payload, "sensor_id": sensor_id})
                event, inserted = store_event(db, record, sensor, asset, user, now())
            except ValidationError as e:
                errors = [".".join(str(k) for k in err["loc"])+": "+err["msg"] for err in e.errors(include_url=False, include_context=False, include_input=False)]
            except HTTPException as e:
                if e.status_code not in (409, 422): raise
                errors = [str(e.detail)]
            if not errors:
                return finish(db, key, hashed, {"outcome": "accepted", "event_id": event.id, "duplicate": not inserted, "snapshot_projection": False})
            payload_hash = hashlib.sha256(json.dumps(body.raw_payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
            insert = sqlite_insert if db.bind.dialect.name == "sqlite" else postgres_insert
            new_id = db.execute(insert(SensorQuarantine).values(id=uid(), sensor_id=sensor_id, payload_hash=payload_hash, raw_payload=body.raw_payload, validation_errors=errors, status="pending", version=1, submitted_by=user.id, created=now()).on_conflict_do_nothing(index_elements=["sensor_id", "payload_hash"]).returning(SensorQuarantine.id)).scalar_one_or_none()
            item = db.scalar(select(SensorQuarantine).where(SensorQuarantine.sensor_id == sensor_id, SensorQuarantine.payload_hash == payload_hash))
            if new_id:
                db.add(Audit(site=asset.site, actor=user.name, action="Sensor payload quarantined", target=f"{asset.tag}/{sensor.channel}", details=f"Review item {item.id}; {len(errors)} validation issue(s). Original object preserved."))
            return finish(db, key, hashed, {"outcome": "quarantined", "item": serialize(item), "duplicate": new_id is None})
        except (IntegrityError, OperationalError):
            db.rollback(); raise HTTPException(409, "Concurrent intake conflicted. Retry with the same request key.")
        except Exception:
            db.rollback(); raise

    @router.get("/api/sensor-quarantine")
    def queue(sensor_id: str, status: Literal["pending", "replayed", "dismissed", "all"] = "pending", limit: int = Query(50, ge=1, le=100), q: str = Query("", max_length=100), cursor: str | None = Query(None, max_length=2048), user: User = Depends(current_user), db: Session = Depends(get_db)):
        sensor, _ = scoped_sensor(db, user, sensor_id)
        return {**queue_page(db, user, sensor, status, q, limit, cursor, serialize), "supported_units":list(UNITS[sensor.channel])}

    @router.post("/api/sensor-quarantine/{id}/replay")
    def replay(id: str, body: Correction, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
        allow(user, "engineer", "admin")
        item, sensor, asset = scoped_item(db, user, id)
        key, hashed, old = idempotent(db, request, user, body.model_dump())
        if old is not None: return old
        if item.status != "pending" or item.version != body.expected_version:
            raise HTTPException(409, "This review item changed or was already resolved. Refresh its history.")
        try:
            record = EventInput(sensor_id=sensor.id, message_id="quarantine:"+id, source="quarantine-review", **body.model_dump(exclude={"expected_version", "reason"}))
            event, _ = store_event(db, record, sensor, asset, user, now())
            changed = db.execute(update(SensorQuarantine).where(SensorQuarantine.id == id, SensorQuarantine.status == "pending", SensorQuarantine.version == body.expected_version).values(status="replayed", version=SensorQuarantine.version+1, corrected_event_id=event.id, corrected_payload=record.model_dump(), reviewer_id=user.id, reviewed_at=now(), review_reason=body.reason).execution_options(synchronize_session=False))
            if changed.rowcount != 1: raise HTTPException(409, "Another reviewer resolved this item. Refresh.")
            db.add(Audit(site=asset.site, actor=user.name, action="Quarantined payload corrected and replayed", target=f"{asset.tag}/{sensor.channel}", details=f"Review item {id}; new event {event.id}; original evidence preserved; reason: {body.reason}"))
            return finish(db, key, hashed, {"outcome": "replayed", "quarantine_id": id, "event_id": event.id, "version": body.expected_version+1, "snapshot_projection": False})
        except (IntegrityError, OperationalError):
            db.rollback(); raise HTTPException(409, "Concurrent review conflicted. Refresh or retry with the same request key.")
        except Exception:
            db.rollback(); raise

    @router.post("/api/sensor-quarantine/{id}/dismiss")
    def dismiss(id: str, body: ReviewReason, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
        allow(user, "engineer", "admin")
        item, sensor, asset = scoped_item(db, user, id)
        key, hashed, old = idempotent(db, request, user, body.model_dump())
        if old is not None: return old
        try:
            changed = db.execute(update(SensorQuarantine).where(SensorQuarantine.id == id, SensorQuarantine.status == "pending", SensorQuarantine.version == body.expected_version).values(status="dismissed", version=SensorQuarantine.version+1, reviewer_id=user.id, reviewed_at=now(), review_reason=body.reason).execution_options(synchronize_session=False))
            if changed.rowcount != 1: raise HTTPException(409, "This item changed or was already resolved. Refresh.")
            db.add(Audit(site=asset.site, actor=user.name, action="Quarantined payload dismissed", target=f"{asset.tag}/{sensor.channel}", details=f"Review item {id}; original evidence preserved; reason: {body.reason}"))
            return finish(db, key, hashed, {"outcome": "dismissed", "quarantine_id": id, "version": body.expected_version+1})
        except (IntegrityError, OperationalError):
            db.rollback(); raise HTTPException(409, "Concurrent review conflicted. Retry with the same request key.")
        except Exception:
            db.rollback(); raise

    return router
