"""Explicit preview/commit of bounded, time-aligned complete sensor frames."""
import hashlib
import json
import math

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from .database import Asset, Audit, Reading, Sensor, SensorEvent, SnapshotProjection, User, now
from .security import allow, current_user, get_db
from .sensor_events import BOUNDS, convert, serialize
from .sensors import CHANNELS

POLICY = "aligned-events-v1"
MAX_SKEW = 5.0


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def candidate(db, asset, latest):
    clock = now()
    sensors = db.scalars(select(Sensor).where(Sensor.asset_id == asset.id)).all()
    sensor_by_channel = {s.channel: s for s in sensors}
    rows, reasons, signature = [], [], []
    for channel, unit in CHANNELS.items():
        sensor = sensor_by_channel.get(channel)
        event = db.scalar(select(SensorEvent).where(SensorEvent.sensor_id == sensor.id).order_by(SensorEvent.observed_at.desc(), SensorEvent.received_at.desc(), SensorEvent.id.desc()).limit(1)) if sensor else None
        if not event:
            reasons.append(f"{channel}: no independent event available.")
            rows.append({"channel": channel, "event": None})
            signature.append([channel, None])
            continue
        record = serialize(event)
        valid = all(math.isfinite(v) for v in (event.raw_value, event.value, event.observed_at, event.received_at))
        if not valid:
            reasons.append(f"{channel}: non-finite stored data.")
            # Do not emit invalid JSON floats from direct database corruption.
            record = {k: None if isinstance(v, float) and not math.isfinite(v) else v for k, v in record.items()}
        if event.unit != unit or sensor.unit != unit or event.conversion != "units-v1":
            reasons.append(f"{channel}: unsupported stored units or conversion version.")
        try:
            normalized = convert(channel, event.raw_unit, event.raw_value)
            if not math.isclose(normalized, event.value, rel_tol=1e-12, abs_tol=1e-10):
                reasons.append(f"{channel}: stored conversion does not match original measurement.")
        except HTTPException:
            reasons.append(f"{channel}: invalid stored measurement.")
        if not BOUNDS[channel][0] <= event.value <= BOUNDS[channel][1]:
            reasons.append(f"{channel}: canonical value outside accepted range.")
        if event.quality != "good":
            reasons.append(f"{channel}: latest event quality is {event.quality}; good is required.")
        if event.observed_at <= 0 or event.observed_at > clock:
            reasons.append(f"{channel}: observation time is invalid or in the future.")
        if clock - event.observed_at > sensor.stale_after_seconds:
            reasons.append(f"{channel}: latest event is stale.")
        rows.append({"channel": channel, "event": record})
        signature.append([channel, record, sensor.version, sensor.stale_after_seconds])
    times = [r["event"]["observed_at"] for r in rows if r["event"] and r["event"]["observed_at"] is not None]
    skew = max(times)-min(times) if len(times) == 4 else None
    timestamp = min(times) if len(times) == 4 else None
    if skew is not None and skew > MAX_SKEW:
        reasons.append("Channel observation times exceed the 5-second alignment window.")
    previous = latest(db, asset.id)
    if timestamp is not None and previous and timestamp <= previous.timestamp:
        reasons.append("A newer or equal equipment snapshot already exists. Pause simulation and submit a new aligned set.")
    frame_hash = digest([POLICY, asset.id, signature])
    preview_signature = digest([frame_hash, previous.id if previous else None, asset.version])
    return {"asset_id": asset.id, "asset_tag": asset.tag, "rows": rows, "ready": not reasons,
            "reasons": reasons, "max_skew_seconds": MAX_SKEW, "skew_seconds": skew,
            "snapshot_timestamp": timestamp, "preview_signature": preview_signature, "frame_hash": frame_hash,
            "policy": POLICY, "latest_snapshot_id": previous.id if previous else None}


class ProjectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str = Field(min_length=1, max_length=36)
    preview_signature: str = Field(pattern=r"^[0-9a-f]{64}$")


def create_projection_router(asset_for, latest, check_episode, idempotent, finish):
    router = APIRouter(prefix="/api/snapshot-projections", tags=["Snapshot alignment"])

    @router.get("/preview")
    def preview(asset_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
        asset = asset_for(db, user, asset_id)
        return candidate(db, asset, latest)

    @router.post("", status_code=201)
    def publish(body: ProjectionInput, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
        allow(user, "engineer", "admin")
        asset = asset_for(db, user, body.asset_id)
        key, hashed, old = idempotent(db, request, user, body.model_dump())
        if old is not None:
            return old
        try:
            frame = candidate(db, asset, latest)
            if frame["preview_signature"] != body.preview_signature:
                raise HTTPException(409, "The alignment preview changed. Refresh and review before publishing.")
            if not frame["ready"]:
                raise HTTPException(422, "; ".join(frame["reasons"]))
            # Serializes competing projection commits for this asset.
            changed = db.execute(update(Asset).where(Asset.id == asset.id, Asset.version == asset.version).values(version=Asset.version+1).execution_options(synchronize_session=False))
            if changed.rowcount != 1:
                raise HTTPException(409, "Equipment changed. Refresh the alignment preview.")
            values = {r["channel"]: r["event"]["value"] for r in frame["rows"]}
            event_ids = {r["channel"]: r["event"]["id"] for r in frame["rows"]}
            reading = Reading(asset_id=asset.id, timestamp=frame["snapshot_timestamp"], quality="good", message_id="projection:"+frame["frame_hash"], **values)
            db.add(reading); db.flush()
            projection = SnapshotProjection(reading_id=reading.id, asset_id=asset.id, frame_hash=frame["frame_hash"], actor_id=user.id, policy=POLICY, **{k+"_event_id":v for k,v in event_ids.items()})
            db.add(projection)
            # Historical concurrent snapshot ingestion must not trigger a current alarm.
            if latest(db, asset.id).id == reading.id:
                check_episode(db, asset, reading)
            db.add(Audit(site=asset.site, actor=user.name, action="Aligned snapshot published", target=asset.tag, details=f"Snapshot {reading.id}; policy {POLICY}; skew {frame['skew_seconds']}s; source events {json.dumps(event_ids, sort_keys=True)}."))
            return finish(db, key, hashed, {"reading_id": reading.id, "event_ids": event_ids, "timestamp": reading.timestamp, "values": values, "policy": POLICY})
        except (IntegrityError, OperationalError):
            db.rollback()
            raise HTTPException(409, "Concurrent projection conflicted. Refresh or retry with the same idempotency key.")
        except Exception:
            db.rollback()
            raise

    @router.get("/history")
    def history(asset_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
        asset_for(db, user, asset_id)
        items = db.scalars(select(SnapshotProjection).where(SnapshotProjection.asset_id == asset_id).order_by(SnapshotProjection.created.desc(), SnapshotProjection.reading_id.desc()).limit(20)).all()
        return {"items": [{"reading_id": p.reading_id, "created": p.created, "policy": p.policy, "event_ids": {k:getattr(p,k+"_event_id") for k in CHANNELS}} for p in items]}

    return router
