"""Explainable triage, observed telemetry comparison and reproducible what-if runs."""

import csv
import hashlib
import io
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Integer, func, select
from sqlalchemy.orm import Session

from .database import Asset, Audit, Episode, Reading, User, WorkOrder, now
from .intelligence import condition, MODEL_VERSION
from .security import allow, current_user, get_db

FIELDS = ("vibration", "temperature", "pressure", "flow")
METHOD = "triage-v1"
LIMITATION = "Demonstration heuristic, not a failure probability, RUL estimate or validated physical model. No equipment settings are changed."


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str = Field(min_length=1, max_length=36)
    baseline_timestamp: float = Field(gt=0, allow_inf_nan=False)
    baseline_signature: str = Field(pattern=r"^[a-f0-9]{64}$")
    vibration: float = Field(ge=0, le=200, allow_inf_nan=False)
    temperature: float = Field(ge=-100, le=500, allow_inf_nan=False)
    pressure: float = Field(ge=0, le=1000, allow_inf_nan=False)
    flow: float = Field(ge=0, le=100000, allow_inf_nan=False)


class SavedScenario(Scenario):
    title: str = Field(min_length=3, max_length=120)


def reading_fingerprint(reading):
    values = {field: getattr(reading, field) for field in (*FIELDS, "timestamp", "quality")}
    return hashlib.sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sample_summary(readings):
    good = [r for r in readings if r.quality == "good"]
    result = {"samples": len(readings), "good_samples": len(good), "channels": {}}
    for field in FIELDS:
        values = [getattr(r, field) for r in good]
        slope = None
        if len(good) >= 2:
            hours = [(r.timestamp - good[0].timestamp) / 3600 for r in good]
            mean_x, mean_y = sum(hours) / len(hours), sum(values) / len(values)
            denominator = sum((x - mean_x) ** 2 for x in hours)
            if denominator:
                slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(hours, values)) / denominator
        result["channels"][field] = {
            "min": min(values) if values else None,
            "max": max(values) if values else None,
            "mean": round(sum(values) / len(values), 3) if values else None,
            "observed_change_per_hour": round(slope, 4) if slope is not None else None,
            "constant_last_12": len(values) >= 12 and len({round(v, 6) for v in values[-12:]}) == 1,
        }
    return result


def create_router(accessible_assets, asset_for, asset_json, reading_json, latest, idempotent, finish):
    router = APIRouter(prefix="/api/lab", tags=["Reliability Lab"])

    def fleet(db, user, site, hours):
        rows = accessible_assets(db, user, site)
        ids = [a.id for a in rows]
        today = datetime.now(timezone(timedelta(hours=4))).date().isoformat()
        episodes = list(db.scalars(select(Episode).where(Episode.asset_id.in_(ids), Episode.state != "resolved")))
        orders = list(db.scalars(select(WorkOrder).where(WorkOrder.asset_id.in_(ids), WorkOrder.status.notin_(["completed", "cancelled"]))))
        counts = {r[0]: (r[1], r[2]) for r in db.execute(
            select(Reading.asset_id, func.count(), func.sum((Reading.quality == "good").cast(Integer)))
            .where(Reading.asset_id.in_(ids), Reading.timestamp >= now() - hours * 3600)
            .group_by(Reading.asset_id)
        )}
        items = []
        for a in rows:
            item = asset_json(db, a)
            active = sum(e.asset_id == a.id for e in episodes)
            overdue = sum(o.asset_id == a.id and o.due_date < today for o in orders)
            components = {
                "condition": round((100 - item["health"]) * .4) if item["health"] is not None else 0,
                "criticality": {"Critical": 20, "High": 15, "Medium": 8, "Low": 3}.get(a.criticality, 8),
                "active_episodes": min(20, active * 10),
                "overdue_work": min(20, overdue * 10),
            }
            score = sum(components.values())
            count, good = counts.get(a.id, (0, 0))
            needs_data = item["health"] is None
            items.append({
                "asset": item, "score": score, "components": components,
                "band": "Data review" if needs_data else "Urgent" if score >= 65 else "Review soon" if score >= 35 else "Routine",
                "needs_data_review": needs_data, "active_episodes": active, "overdue_orders": overdue,
                "samples": count, "good_samples": good or 0,
                "quality_percent": round(100 * (good or 0) / count, 1) if count else None,
                "reasons": [f"Condition contributes {components['condition']}/40" if not needs_data else "Condition unavailable: inspect missing, stale or poor-quality readings", f"{a.criticality} criticality contributes {components['criticality']}/20", f"{active} active episodes contribute {components['active_episodes']}/20", f"{overdue} overdue orders contribute {components['overdue_work']}/20"],
            })
        items.sort(key=lambda x: (not x["needs_data_review"], -x["score"], x["asset"]["tag"]))
        return {
            "generated_at": now(), "hours": hours, "method": METHOD,
            "limitation": LIMITATION,
            "summary": {"assets": len(items), "data_review": sum(x["needs_data_review"] for x in items), "urgent": sum(x["band"] == "Urgent" for x in items), "overdue_orders": sum(x["overdue_orders"] for x in items), "samples": sum(x["samples"] for x in items)},
            "items": items,
        }

    @router.get("/fleet")
    def fleet_view(site: str | None = None, hours: int = Query(168, ge=1, le=720), user: User = Depends(current_user), db: Session = Depends(get_db)):
        return fleet(db, user, site, hours)

    @router.get("/export.csv")
    def export(site: str | None = None, hours: int = Query(168, ge=1, le=720), user: User = Depends(current_user), db: Session = Depends(get_db)):
        result = fleet(db, user, site, hours)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Asset", "Name", "Site", "Triage score (not probability)", "Queue", "Condition", "Data quality %", "Window samples", "Overdue work", "Reasons", "Method"])
        for item in result["items"]:
            a = item["asset"]
            values = [a["tag"], a["name"], a["site"], item["score"], item["band"], a["health"], item["quality_percent"], item["samples"], item["overdue_orders"], "; ".join(item["reasons"]), METHOD]
            writer.writerow(["'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v for v in values])
        return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="sentinel-reliability-brief.csv"'})

    @router.get("/compare")
    def compare(ids: list[str] = Query(min_length=1, max_length=3), hours: int = Query(168, ge=1, le=720), user: User = Depends(current_user), db: Session = Depends(get_db)):
        if len(set(ids)) != len(ids):
            raise HTTPException(422, "Select distinct assets.")
        assets = [asset_for(db, user, id) for id in ids]
        result = []
        for a in assets:
            samples = list(db.scalars(select(Reading).where(Reading.asset_id == a.id, Reading.timestamp >= now() - hours * 3600).order_by(Reading.timestamp.desc(), Reading.id.desc()).limit(300)))[::-1]
            result.append({"asset": asset_json(db, a), "readings": [reading_json(r) for r in samples], "statistics": sample_summary(samples)})
        return {"hours": hours, "sample_limit": 300, "series": result, "note": "Most recent 300 samples per asset in the selected window. Statistics exclude non-good readings; curves display only good samples. Observed drift is a fitted historical slope, not a forecast."}

    def evaluate(body, db, user):
        a = asset_for(db, user, body.asset_id)
        baseline = latest(db, a.id)
        if not baseline or baseline.quality != "good":
            raise HTTPException(409, "A good-quality baseline reading is required. Generate or ingest a valid snapshot first.")
        if baseline.timestamp != body.baseline_timestamp or reading_fingerprint(baseline) != body.baseline_signature:
            raise HTTPException(409, "The baseline changed. Refresh the workspace and run the scenario again.")
        values = {f: getattr(body, f) for f in FIELDS}
        projected = condition(SimpleNamespace(**values, quality="good"), a.threshold)
        measured = condition(baseline, a.threshold)
        return {"asset_id": a.id, "asset_tag": a.tag, "site": a.site, "baseline": reading_json(baseline), "baseline_stale": now() - baseline.timestamp > 3600, "inputs": values, "baseline_condition": measured, "scenario_condition": projected, "health_delta": projected["health"] - measured["health"], "model_version": MODEL_VERSION, "method": "condition-whatif-v1", "calculated_at": now(), "limitation": LIMITATION}

    @router.post("/simulate")
    def simulate(body: Scenario, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return evaluate(body, db, user)

    @router.post("/scenarios", status_code=201)
    def save(body: SavedScenario, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
        allow(user, "engineer", "admin")
        asset_for(db, user, body.asset_id)
        key, digest, old = idempotent(db, request, user, body.model_dump())
        if old:
            return old
        result = evaluate(body, db, user)
        record = Audit(site=result["site"], actor=user.name, action="Scenario saved", target=result["asset_tag"], details=json.dumps({"title": body.title, "result": result}))
        db.add(record)
        db.flush()
        payload = {"id": record.id, "title": body.title, "actor": user.name, "created": record.created, "result": result}
        return finish(db, key, digest, payload)

    @router.get("/scenarios")
    def history(site: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
        accessible_assets(db, user, site)
        events = db.scalars(select(Audit).where(Audit.site.in_([site] if site else user.sites), Audit.action == "Scenario saved").order_by(Audit.created.desc()).limit(25))
        return [{"id": e.id, "actor": e.actor, "created": e.created, **json.loads(e.details)} for e in events]

    return router
