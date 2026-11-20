"""Stable registry identities for the existing four-channel equipment snapshots."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as postgres_insert

from .database import Asset, Audit, Sensor, User, now
from .security import allow, current_user, get_db

CHANNELS = {"vibration": "mm/s", "temperature": "degC", "pressure": "bar", "flow": "m3/h"}


def ensure_sensors(db, assets):
    insert = sqlite_insert if db.bind.dialect.name == "sqlite" else postgres_insert
    for asset in assets:
        for channel, unit in CHANNELS.items():
            values = {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"industrialai-sentinel/sensor/{asset.id}/{channel}")), "asset_id": asset.id, "channel": channel, "unit": unit, "label": channel.title(), "expected_interval_seconds": 300, "stale_after_seconds": 900, "version": 1, "created": now()}
            db.execute(insert(Sensor).values(**values).on_conflict_do_nothing(index_elements=["asset_id", "channel"]))


class SensorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    label: str = Field(min_length=1, max_length=100)
    expected_interval_seconds: int = Field(ge=1, le=86400)
    stale_after_seconds: int = Field(ge=1, le=604800)

    @model_validator(mode="after")
    def freshness_budget(self):
        if not self.label.strip():
            raise ValueError("Sensor label cannot be blank.")
        if self.stale_after_seconds < self.expected_interval_seconds:
            raise ValueError("Freshness limit must be at least the expected reporting interval.")
        return self


def create_sensor_router(accessible_assets, asset_for, latest):
    router = APIRouter(prefix="/api/sensors", tags=["Sensor registry"])

    def serialize(sensor, asset, reading):
        age = max(0, int(now() - reading.timestamp)) if reading else None
        freshness = "missing" if age is None else "stale" if age > sensor.stale_after_seconds else "fresh"
        quality = reading.quality if reading else "unknown"
        return {"id": sensor.id, "asset_id": asset.id, "asset_tag": asset.tag, "asset_name": asset.name, "site": asset.site, "channel": sensor.channel, "unit": sensor.unit, "label": sensor.label, "expected_interval_seconds": sensor.expected_interval_seconds, "stale_after_seconds": sensor.stale_after_seconds, "version": sensor.version, "created": sensor.created, "latest_value": getattr(reading, sensor.channel) if reading else None, "latest_timestamp": reading.timestamp if reading else None, "age_seconds": age, "quality": quality, "freshness": freshness, "status": "unknown" if freshness == "missing" else "warning" if freshness == "stale" or quality != "good" else "healthy", "mapping": "equipment-snapshot-v1"}

    @router.get("")
    def registry(site: str | None = None, asset_id: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
        assets = accessible_assets(db, user, site)
        if asset_id:
            asset_for(db, user, asset_id)
            assets = [a for a in assets if a.id == asset_id]
        by_id = {a.id: a for a in assets}
        readings = {a.id: latest(db, a.id) for a in assets}
        rows = list(db.scalars(select(Sensor).where(Sensor.asset_id.in_(by_id)).order_by(Sensor.asset_id, Sensor.channel)))
        items = [serialize(s, by_id[s.asset_id], readings[s.asset_id]) for s in rows]
        items.sort(key=lambda r: (r["asset_tag"], r["channel"]))
        return {"items": items, "summary": {"sensors": len(items), "fresh_good": sum(i["freshness"] == "fresh" and i["quality"] == "good" for i in items), "stale": sum(i["freshness"] == "stale" for i in items), "missing": sum(i["freshness"] == "missing" for i in items), "quality_review": sum(i["quality"] in ("bad", "suspect") for i in items)}, "mapping": "One stable registry identity per asset/channel. Table values and freshness use complete equipment snapshots."}

    @router.patch("/{id}")
    def configure(id: str, body: SensorConfig, user: User = Depends(current_user), db: Session = Depends(get_db)):
        allow(user, "engineer", "admin")
        sensor = db.get(Sensor, id)
        if not sensor:
            raise HTTPException(404, "Sensor not found.")
        asset = asset_for(db, user, sensor.asset_id)
        values = body.model_dump(exclude={"expected_version"})
        values["label"] = values["label"].strip()
        changed = db.execute(update(Sensor).where(Sensor.id == id, Sensor.version == body.expected_version).values(**values, version=Sensor.version+1).execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            raise HTTPException(409, "This sensor changed. Refresh before editing its configuration.")
        db.add(Audit(site=asset.site, actor=user.name, action="Sensor configuration changed", target=f"{asset.tag}/{sensor.channel}", details=f"Sensor {id}; version {body.expected_version+1}; expected interval {body.expected_interval_seconds}s; stale after {body.stale_after_seconds}s. Units and telemetry unchanged."))
        db.commit()
        db.refresh(sensor)
        return serialize(sensor, asset, latest(db, asset.id))

    return router
