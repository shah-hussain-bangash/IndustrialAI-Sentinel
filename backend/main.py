"""Runnable local reference implementation. See docs/IMPLEMENTATION_STATUS.md."""

import csv
import hashlib
import io
import json
import math
import os
import secrets
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import numpy as np
from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict, field_validator, SecretStr
from pypdf import PdfReader
from sqlalchemy import select, update, func, delete, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import *
from .security import (
    current_user,
    get_db,
    allow,
    site_allowed,
    COOKIE,
    DEMO_ENABLED,
    DEMO_PASSWORD,
    password_valid,
    password_hash,
    token_hash,
    canonicalize_user,
)
from .seed import initialize, payload_hash, SITES
from .intelligence import condition, make_investigation, search_documents, model_metrics
from .reliability import create_router, reading_fingerprint
from .sensors import create_sensor_router, ensure_sensors
from .sensor_events import create_event_router
from .projections import create_projection_router
from .quarantine import create_quarantine_router
from .recovery import create_recovery_router
from .originals import create_original_router, original_metadata, filename as original_filename
from .gateways import create_gateway_router
from fastapi.exceptions import RequestValidationError
from .foundation import create_foundation_router
from .team import create_team_router
from .accounts import create_account_router
from .mfa import create_mfa_router,login_challenge
from .mfa_core import required as mfa_required
from .sites import create_site_router
from .condition_rules import create_condition_rule_router
from .live_rules import create_live_rule_router, process_snapshot
from .rule_reviews import create_rule_review_router, create_rule_inbox_router
from .rule_assignments import create_rule_assignment_router
from .match_investigations import create_match_investigation_router
from .maintenance_windows import create_maintenance_window_router
from .maintenance_controls import create_maintenance_control_router
from .notification_plans import create_notification_plan_router
from .notification_reviews import create_notification_review_router


@asynccontextmanager
async def lifespan(app):
    existing = inspect(engine)
    if existing.has_table("assets") and "site_id" not in {c["name"] for c in existing.get_columns("assets")}:
        raise RuntimeError("Site schema upgrade required. Stop Sentinel and run scripts/upgrade_database.py before restarting.")
    if existing.has_table("assets") and not existing.has_table("sensor_events"):
        raise RuntimeError("Sensor-event schema upgrade required. Stop Sentinel and run scripts/upgrade_database.py.")
    if existing.has_table("assets") and not existing.has_table("snapshot_projections"):
        raise RuntimeError("Snapshot alignment schema upgrade required. Stop Sentinel and run scripts/upgrade_database.py.")
    if existing.has_table("assets") and not existing.has_table("sensor_quarantine"):
        raise RuntimeError("Sensor data review schema upgrade required. Stop Sentinel and run scripts/upgrade_database.py.")
    if existing.has_table("assets") and not existing.has_table("document_originals"):
        raise RuntimeError("Original document archive schema upgrade required. Stop Sentinel and run scripts/upgrade_database.py.")
    if existing.has_table("assets") and not existing.has_table("telemetry_gateways"):
        raise RuntimeError("Telemetry gateway schema upgrade required. Stop Sentinel and run scripts/upgrade_database.py.")
    if existing.has_table("assets") and not all(existing.has_table(t) for t in ("organization", "site_areas", "equipment_systems", "equipment_placements")):
        raise RuntimeError("Organization hierarchy upgrade required. Stop Sentinel and run scripts/upgrade_database.py before restarting.")
    if existing.has_table("assets") and not existing.has_table("account_links"):
        raise RuntimeError("Account email upgrade required. Stop Sentinel and run scripts/upgrade_database.py.")
    if existing.has_table("assets") and not existing.has_table("mfa_credentials"):
        raise RuntimeError("Administrator MFA upgrade required. Stop Sentinel and run scripts/upgrade_database.py.")
    if existing.has_table("assets") and not all(existing.has_table(t) for t in ("condition_rules", "condition_rule_revisions")):
        raise RuntimeError("Condition rule draft upgrade required. Stop Sentinel and run scripts/upgrade_database.py.")
    if existing.has_table("assets") and not all(existing.has_table(t) for t in ("condition_rule_deployments", "condition_rule_matches")):
        raise RuntimeError("Condition rule activation upgrade required. Stop Sentinel and run scripts/upgrade_database.py.")
    if existing.has_table("assets") and not existing.has_table("condition_rule_reviews"):
        raise RuntimeError("Condition rule review upgrade required. Stop Sentinel and run scripts/upgrade_database.py.")
    if existing.has_table("assets") and not existing.has_table("condition_rule_assignments"):
        raise RuntimeError("Condition review ownership upgrade required. Stop Sentinel and run scripts/upgrade_database.py.")
    if existing.has_table("assets") and not existing.has_table("condition_match_investigations"):
        raise RuntimeError("Condition investigation link upgrade required. Stop Sentinel and run scripts/upgrade_database.py.")
    if existing.has_table("assets") and not all(existing.has_table(t) for t in ("maintenance_window_drafts", "maintenance_window_revisions")):
        raise RuntimeError("Maintenance-window draft upgrade required. Stop Sentinel and run scripts/upgrade_database.py.")
    if existing.has_table("assets") and not existing.has_table("maintenance_window_reviews"):
        raise RuntimeError("Maintenance-window review upgrade required. Stop Sentinel and run scripts/upgrade_database.py.")
    if existing.has_table("assets") and not all(existing.has_table(t) for t in ("maintenance_window_controls", "maintenance_window_suppressions")):
        raise RuntimeError("Maintenance-window control upgrade required. Stop Sentinel and run scripts/upgrade_database.py.")
    if existing.has_table("assets") and not existing.has_table("notification_plan_revisions"):
        raise RuntimeError("Notification plan draft upgrade required. Stop Sentinel and run scripts/upgrade_database.py.")
    if existing.has_table("assets") and not existing.has_table("notification_plan_reviews"):
        raise RuntimeError("Notification planning review upgrade required. Stop Sentinel and run scripts/upgrade_database.py.")
    initialize()
    if not inspect(engine).has_table("account_links"):
        raise RuntimeError("Account email upgrade required. Stop Sentinel and run scripts/upgrade_database.py.")
    if not inspect(engine).has_table("sites"):
        raise RuntimeError("Site schema is missing. Stop the server and run scripts/upgrade_database.py before restarting.")
    with SessionLocal() as db:
        ensure_sensors(db, list(db.scalars(select(Asset))))
        db.commit()
    yield


app = FastAPI(
    title="IndustrialAI Sentinel",
    version="1.0.0",
    lifespan=lifespan,
    description="Local reference implementation. Telemetry, manuals and CMMS are synthetic demonstration data; consult implementation status before production use.",
)
LOGIN_ATTEMPTS = defaultdict(list)
REQUEST_TIMES = []
ALLOWED_ORIGINS = set(
    os.getenv(
        "ALLOWED_ORIGINS",
        "http://127.0.0.1:5187,http://localhost:5187,http://127.0.0.1:8127,http://localhost:8127",
    ).split(",")
)


@app.middleware("http")
async def request_guard(request, call_next):
    start = time.perf_counter()
    request_id = secrets.token_hex(8)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and origin not in ALLOWED_ORIGINS:
            return JSONResponse(
                {"detail": "Origin is not allowed.", "request_id": request_id}, status_code=403
            )
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > 11 * 1024 * 1024):
            return JSONResponse(
                {"detail": "Request is too large. Maximum upload is 10 MB."}, status_code=413
            )
    response = await call_next(request)
    response.headers.update(
        {
            "X-Request-ID": request_id,
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "same-origin",
            "X-Frame-Options": "DENY",
            "Cache-Control": "no-store" if request.url.path.startswith("/api") else "no-cache",
        }
    )
    if request.url.path.startswith("/api"):
        REQUEST_TIMES.append((time.perf_counter() - start) * 1000)
        del REQUEST_TIMES[:-500]
    return response


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    # Do not reflect raw payloads or non-JSON floats in validation responses.
    return JSONResponse(status_code=422, content={"detail": [{k: e[k] for k in ("loc", "msg", "type") if k in e} for e in exc.errors()]})


@app.exception_handler(IntegrityError)
async def integrity_handler(request, exc):
    return JSONResponse(
        {"detail": "A conflicting record or concurrent update exists. Refresh and retry."},
        status_code=409,
    )


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Strict):
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)


class PasswordChange(Strict):
    current_password: SecretStr
    new_password: SecretStr


class AssetCreate(Strict):
    tag: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=3, max_length=160)
    kind: Literal["Pump", "Compressor", "Motor", "Turbine"] = "Pump"
    site: str
    location: str = Field(min_length=2, max_length=100)
    criticality: Literal["Critical", "High", "Medium", "Low"] = "High"
    threshold: float = Field(default=4.5, gt=0, le=100, allow_inf_nan=False)


class Investigate(Strict):
    asset_id: str
    title: str = Field(default="", max_length=200)


class DraftEdit(Strict):
    expected_version: int = Field(ge=1)
    recommendation: str = Field(min_length=10, max_length=4000)
    checklist: list[str] = Field(min_length=1, max_length=20)


class Decision(Strict):
    expected_version: int = Field(ge=1)
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=3, max_length=1500)


class OrderCreate(Strict):
    investigation_id: str
    expected_version: int = Field(ge=1)
    due_date: str
    assignee: str = Field(default="Unassigned", max_length=100)

    @field_validator("due_date")
    @classmethod
    def date_valid(cls, v):
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Use a valid YYYY-MM-DD date.")
        return v


class VersionCommand(Strict):
    expected_version: int = Field(ge=1)


class Dispatch(VersionCommand):
    simulate_timeout: bool = False


class OrderTransition(VersionCommand):
    status: Literal["in_progress", "completed", "cancelled"]
    outcome: str = Field(default="", max_length=3000)


class EpisodeCommand(VersionCommand):
    state: Literal["acknowledged", "under_review", "resolved"]


class Tick(Strict):
    scenario: Literal["normal", "bearing_trend", "recovery"] = "normal"


class Question(Strict):
    question: str = Field(min_length=3, max_length=1500)
    site: str | None = None
    kind: str | None = None


class TelemetryRecord(Strict):
    asset_id: str
    timestamp: float = Field(gt=0, allow_inf_nan=False)
    vibration: float = Field(ge=0, le=200, allow_inf_nan=False)
    temperature: float = Field(ge=-100, le=500, allow_inf_nan=False)
    pressure: float = Field(ge=0, le=1000, allow_inf_nan=False)
    flow: float = Field(ge=0, le=100000, allow_inf_nan=False)
    quality: Literal["good", "suspect", "bad"] = "good"
    message_id: str = Field(min_length=5, max_length=100)


class Batch(Strict):
    records: list[TelemetryRecord] = Field(min_length=1, max_length=500)


class Preferences(Strict):
    compact: bool = False
    email_digest: bool = False
    display_timezone: Literal["Asia/Dubai", "UTC"] = "Asia/Dubai"


def audit(db, user, site, action, target, details=""):
    db.add(Audit(site=site, actor=user.name, action=action, target=target, details=details))


def accessible_assets(db, user, site=None):
    if site:
        site_allowed(user, site)
    return list(
        db.scalars(
            select(Asset).where(Asset.site.in_([site] if site else user.sites)).order_by(Asset.tag)
        )
    )


def asset_for(db, user, id):
    asset = db.get(Asset, id)
    if not asset:
        raise HTTPException(404, "Asset not found.")
    site_allowed(user, asset.site)
    return asset


def latest(db, asset_id):
    return db.scalar(
        select(Reading)
        .where(Reading.asset_id == asset_id)
        .order_by(Reading.timestamp.desc())
        .limit(1)
    )


def asset_json(db, asset):
    reading = latest(db, asset.id)
    c = condition(reading, asset.threshold)
    if reading and now() - reading.timestamp > 3600:
        c = {**c, "health": None, "status": "unknown", "anomaly": False}
    return {
        "id": asset.id,
        "tag": asset.tag,
        "name": asset.name,
        "kind": asset.kind,
        "site": asset.site,
        "site_id": asset.site_id,
        "location": asset.location,
        "criticality": asset.criticality,
        "manufacturer": asset.manufacturer,
        "installed": asset.installed,
        "version": asset.version,
        "threshold": asset.threshold,
        **c,
        "reading": reading_json(reading) if reading else None,
        "freshness_seconds": max(0, round(now() - reading.timestamp)) if reading else None,
        "sensor_count": db.scalar(select(func.count()).select_from(Sensor).where(Sensor.asset_id == asset.id)),
        "source": "aligned_sensor_events" if reading and db.get(SnapshotProjection, reading.id) else "simulation" if DEMO_ENABLED else "ingestion",
        "vibration_trend": list(
            db.scalars(
                select(Reading.vibration)
                .where(Reading.asset_id == asset.id)
                .order_by(Reading.timestamp.desc())
                .limit(28)
            )
        )[::-1],
    }


def reading_json(r):
    return {
        "fingerprint": reading_fingerprint(r),
        **{
        k: getattr(r, k)
        for k in ["timestamp", "vibration", "temperature", "pressure", "flow", "quality"]
        },
    }


def user_json(user):
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "sites": user.sites,
        "site_ids": getattr(user, "_site_ids", []),
        "mfa_setup_required": bool(getattr(user,"_mfa_setup_required",False)),
    }


def episode_json(db, e):
    a = db.get(Asset, e.asset_id)
    return {
        "id": e.id,
        "asset_id": a.id,
        "asset_tag": a.tag,
        "asset_name": a.name,
        "site": a.site,
        "title": e.title,
        "severity": e.severity,
        "state": e.state,
        "created": e.created,
        "version": e.version,
    }


def investigation_for(db, user, id):
    inv = db.get(Investigation, id)
    if not inv:
        raise HTTPException(404, "Investigation not found.")
    asset = asset_for(db, user, inv.asset_id)
    return inv, asset


def inv_json(db, inv):
    a = db.get(Asset, inv.asset_id)
    creator = db.get(User, inv.creator_id)
    approver = db.get(User, inv.approved_by) if inv.approved_by else None
    return {
        "id": inv.id,
        "asset_id": a.id,
        "asset_tag": a.tag,
        "asset_name": a.name,
        "site": a.site,
        "title": inv.title,
        "state": inv.state,
        "created": inv.created,
        "version": inv.version,
        "payload": inv.payload,
        "payload_hash": inv.payload_hash,
        "creator": creator.name,
        "creator_id": creator.id,
        "approver": approver.name if approver else None,
        "approved_until": inv.approved_until,
        "decision_reason": inv.decision_reason,
    }


def order_for(db, user, id):
    order = db.get(WorkOrder, id)
    if not order:
        raise HTTPException(404, "Work order not found.")
    asset = asset_for(db, user, order.asset_id)
    return order, asset


def order_json(db, o):
    a = db.get(Asset, o.asset_id)
    return {
        **{
            k: getattr(o, k)
            for k in [
                "id",
                "reference",
                "asset_id",
                "investigation_id",
                "title",
                "priority",
                "status",
                "assignee",
                "due_date",
                "external_ref",
                "created",
                "version",
                "outcome",
            ]
        },
        "asset_tag": a.tag,
        "asset_name": a.name,
        "site": a.site,
        "integration": "Local CMMS simulator",
    }


def idempotent(db, request, user, body):
    key = request.headers.get("Idempotency-Key", "")
    if len(key) < 8 or len(key) > 100:
        raise HTTPException(422, "Provide an Idempotency-Key between 8 and 100 characters.")
    scoped = f"{user.id}:{request.url.path}:{key}"
    digest = payload_hash(body)
    old = db.get(Idempotency, scoped)
    if old and old.request_hash != digest:
        raise HTTPException(409, "This idempotency key was already used for different content.")
    return scoped, digest, old.response if old else None


def finish(db, key, digest, result):
    db.add(Idempotency(key=key, request_hash=digest, response=result))
    db.commit()
    return result


def check_version(actual, expected):
    if actual != expected:
        raise HTTPException(409, "This record changed. Refresh before continuing.")


def atomic_version(db, model, id, version, values):
    changed = db.execute(
        update(model)
        .where(model.id == id, model.version == version)
        .values(**values, version=version + 1)
    )
    if changed.rowcount != 1:
        raise HTTPException(409, "Another action changed this record. Refresh and try again.")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "mode": "demo" if DEMO_ENABLED else "local",
        "database": "sqlite" if DATABASE_URL.startswith("sqlite") else "postgresql",
    }


@app.get("/api/auth/demo")
def demo_accounts(db: Session = Depends(get_db)):
    if not DEMO_ENABLED:
        return {"enabled": False, "accounts": []}
    return {
        "enabled": True,
        "password": DEMO_PASSWORD,
        "accounts": [
            user_json(canonicalize_user(u, db))
            for u in db.scalars(select(User).order_by(User.email))
            if u.role not in ('disabled', 'invited') and password_valid(DEMO_PASSWORD, u.password_hash)
        ],
    }


@app.post("/api/auth/login")
def login(body: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "local"
    t = now()
    attempts = LOGIN_ATTEMPTS[ip]
    attempts[:] = [x for x in attempts if t - x < 60]
    if len(attempts) >= 15:
        raise HTTPException(429, "Too many sign-in attempts. Wait a minute before retrying.")
    attempts.append(t)
    user = db.scalar(select(User).where(User.email == body.email.lower().strip()))
    if not user or user.role in ('disabled', 'invited') or not password_valid(body.password, user.password_hash):
        raise HTTPException(401, "Email or password is incorrect.")
    credential = db.get(MfaCredential,user.id)
    if credential and credential.enabled:
        return login_challenge(db,user,request,response)
    user._mfa_setup_required = user.role=='admin' and mfa_required(db)
    token = secrets.token_urlsafe(36)
    csrf = secrets.token_urlsafe(24)
    previous = request.cookies.get(COOKIE)
    if previous:
        old = db.get(LoginSession, token_hash(previous))
        if old:
            db.delete(old)
    db.add(
        LoginSession(token_hash=token_hash(token), user_id=user.id, csrf=csrf, expires=t + 28800)
    )
    db.commit()
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        samesite="strict",
        secure=os.getenv("COOKIE_SECURE", "false") == "true",
        max_age=28800,
        path="/",
    )
    return {"user": user_json(canonicalize_user(user, db)), "csrf": csrf}


@app.get("/api/auth/me")
def me(request: Request, user: User = Depends(current_user)):
    return {"user": user_json(user), "csrf": request.state.csrf}


@app.post("/api/auth/logout")
def logout(
    request: Request,
    response: Response,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    session = db.get(LoginSession, token_hash(request.cookies.get(COOKIE, "")))
    if session:
        db.delete(session)
        db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@app.post("/api/auth/password")
def change_password(
    body: PasswordChange,
    response: Response,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    attempts = LOGIN_ATTEMPTS["password:" + user.id]
    t = now()
    attempts[:] = [x for x in attempts if t - x < 60]
    if len(attempts) >= 5:
        raise HTTPException(429, "Too many password attempts. Wait a minute before retrying.")
    attempts.append(t)
    current = body.current_password.get_secret_value()
    new = body.new_password.get_secret_value()
    if len(current) > 200 or not 15 <= len(new) <= 128 or not new.strip():
        raise HTTPException(422, "Choose a password between 15 and 128 characters.")
    if not password_valid(current, user.password_hash):
        raise HTTPException(403, "Your current password is incorrect.")
    if new == current or new == DEMO_PASSWORD:
        raise HTTPException(422, "Choose a new password different from your current password and the shared demo password.")
    changed = db.execute(
        update(User)
        .where(User.id == user.id, User.password_hash == user.password_hash)
        .values(password_hash=password_hash(new))
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        raise HTTPException(409, "Your account changed. Sign in again before updating your password.")
    db.execute(delete(LoginSession).where(LoginSession.user_id == user.id))
    for site in user.sites:
        audit(db, user, site, "Password changed", user.email, "All account sessions revoked.")
    db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True, "message": "Password updated. Sign in with your new password."}


@app.get("/api/assets")
def assets(
    site: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return [asset_json(db, a) for a in accessible_assets(db, user, site)]


@app.post("/api/assets", status_code=201)
def add_asset(
    body: AssetCreate,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    allow(user, "engineer", "admin")
    site_allowed(user, body.site)
    key, h, old = idempotent(db, request, user, body.model_dump())
    if old:
        return old
    a = Asset(**body.model_dump())
    db.add(a)
    db.flush()
    ensure_sensors(db, [a])
    audit(db, user, a.site, "Asset registered", a.tag)
    return finish(db, key, h, asset_json(db, a))


@app.get("/api/assets/{id}")
def asset_detail(id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    a = asset_for(db, user, id)
    readings = list(
        db.scalars(
            select(Reading)
            .where(Reading.asset_id == id)
            .order_by(Reading.timestamp.desc())
            .limit(180)
        )
    )[::-1]
    episodes = list(
        db.scalars(select(Episode).where(Episode.asset_id == id).order_by(Episode.created.desc()))
    )
    return {
        "asset": asset_json(db, a),
        "readings": [reading_json(r) for r in readings],
        "episodes": [episode_json(db, e) for e in episodes],
    }


@app.get("/api/overview")
def overview(
    site: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    rows = accessible_assets(db, user, site)
    items = [asset_json(db, a) for a in rows]
    ids = [a.id for a in rows]
    episodes = list(
        db.scalars(
            select(Episode).where(Episode.asset_id.in_(ids)).order_by(Episode.created.desc())
        )
    )
    orders = list(db.scalars(select(WorkOrder).where(WorkOrder.asset_id.in_(ids))))
    invs = list(db.scalars(select(Investigation).where(Investigation.asset_id.in_(ids))))
    values = [a["health"] for a in items if a["health"] is not None]
    r = latest(db, ids[0]) if ids else None
    readings = (
        list(
            db.scalars(
                select(Reading)
                .where(Reading.asset_id == ids[0])
                .order_by(Reading.timestamp.desc())
                .limit(80)
            )
        )[::-1]
        if ids
        else []
    )
    return {
        "assets": items,
        "episodes": [episode_json(db, e) for e in episodes[:6]],
        "stats": {
            "assets": len(items),
            "healthy": sum(a["status"] == "healthy" for a in items),
            "attention": sum(a["status"] in ("critical", "warning") for a in items),
            "health": round(sum(values) / len(values)) if values else None,
            "sensors": sum(a["sensor_count"] for a in items),
            "pending_reviews": sum(i.state == "awaiting_review" for i in invs),
            "open_orders": sum(o.status not in ("completed", "cancelled") for o in orders),
        },
        "trend": [reading_json(x) for x in readings],
        "trend_asset": rows[0].tag if rows else None,
        "model": model_metrics(),
        "mode": "simulation" if DEMO_ENABLED else "ingestion",
    }


@app.get("/api/episodes")
def episodes(
    site: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    ids = [a.id for a in accessible_assets(db, user, site)]
    return [
        episode_json(db, e)
        for e in db.scalars(
            select(Episode).where(Episode.asset_id.in_(ids)).order_by(Episode.created.desc())
        )
    ]


@app.post("/api/episodes/{id}/transition")
def episode_transition(
    id: str, body: EpisodeCommand, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    allow(user, "engineer", "admin")
    e = db.get(Episode, id)
    if not e:
        raise HTTPException(404, "Episode not found.")
    a = asset_for(db, user, e.asset_id)
    check_version(e.version, body.expected_version)
    allowed = {
        "active": ["acknowledged"],
        "acknowledged": ["under_review", "resolved"],
        "under_review": ["resolved"],
        "resolved": [],
    }
    if body.state not in allowed[e.state]:
        raise HTTPException(409, "This alarm transition is not available.")
    atomic_version(db, Episode, id, e.version, {"state": body.state})
    audit(db, user, a.site, "Alarm " + body.state, a.tag)
    db.commit()
    db.refresh(e)
    return episode_json(db, e)


def check_episode(db, a, r):
    process_snapshot(db, a, r)
    c = condition(r, a.threshold)
    if c["status"] in ("warning", "critical"):
        open_episode = db.scalar(
            select(Episode).where(Episode.asset_id == a.id, Episode.state != "resolved").limit(1)
        )
        if not open_episode:
            db.add(
                Episode(
                    asset_id=a.id,
                    title="Condition outside demonstration baseline",
                    severity=c["status"],
                )
            )


@app.post("/api/telemetry/batches")
def ingest(
    body: Batch, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    allow(user, "engineer", "admin")
    key, h, old = idempotent(db, request, user, body.model_dump())
    if old:
        return old
    accepted = duplicates = 0
    for row in body.records:
        a = asset_for(db, user, row.asset_id)
        if row.timestamp > now() + 120:
            raise HTTPException(422, "Timestamp is more than 120 seconds in the future.")
        previous = db.scalar(select(Reading).where(Reading.message_id == row.message_id))
        if previous:
            if any(
                getattr(previous, k) != v for k, v in row.model_dump().items() if k != "message_id"
            ):
                raise HTTPException(
                    409, "A message identity cannot be reused with changed content."
                )
            duplicates += 1
            continue
        r = Reading(**row.model_dump())
        db.add(r)
        db.flush()
        accepted += 1
        newest = latest(db, a.id)
        if newest.id == r.id:
            check_episode(db, a, r)
    audit(
        db,
        user,
        user.sites[0],
        "Telemetry ingested",
        f"{accepted} snapshots",
        f"{duplicates} exact duplicates ignored",
    )
    return finish(db, key, h, {"accepted": accepted, "duplicates": duplicates})


@app.post("/api/simulation/tick")
def tick(
    body: Tick, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    if not DEMO_ENABLED:
        raise HTTPException(403, "Simulation is disabled.")
    allow(user, "engineer", "admin")
    key, h, old = idempotent(db, request, user, body.model_dump())
    if old:
        return old
    rng = np.random.default_rng(int(now() * 1000) % 2**32)
    for a in accessible_assets(db, user):
        prev = latest(db, a.id)
        if not prev:
            r = Reading(
                    asset_id=a.id,
                    timestamp=now(),
                    vibration=2.2,
                    temperature=65.0,
                    pressure=5.2,
                    flow=120.0,
                )
            db.add(r)
            check_episode(db, a, r)
            continue
        vib = max(0.3, prev.vibration + rng.normal(0, 0.07))
        temp = prev.temperature + rng.normal(0, 0.25)
        if a.tag == "P-101":
            if body.scenario == "bearing_trend":
                vib = min(9, vib + 0.22)
                temp = min(100, temp + 0.5)
            elif body.scenario == "recovery":
                vib = max(2.1, vib - 0.28)
                temp = max(66, temp - 0.7)
        r = Reading(
            asset_id=a.id,
            timestamp=now(),
            vibration=round(vib, 3),
            temperature=round(temp, 2),
            pressure=round(max(0.1, prev.pressure + rng.normal(0, 0.04)), 3),
            flow=round(max(0, prev.flow + rng.normal(0, 1)), 2),
        )
        db.add(r)
        check_episode(db, a, r)
    return finish(db, key, h, {"ok": True, "timestamp": now(), "scenario": body.scenario})


@app.get("/api/documents")
def documents(
    site: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    if site:
        site_allowed(user, site)
    docs = db.scalars(
        select(Document)
        .where(Document.site.in_([site] if site else user.sites))
        .order_by(Document.created.desc())
    )
    return [
        {
            "id": d.id,
            "title": d.title,
            "filename": d.filename,
            "site": d.site,
            "site_id": d.site_id,
            "kind": d.kind,
            "version": d.version,
            "page_count": len(d.pages),
            "created": d.created,
            "checksum": d.checksum,
            **original_metadata(db,d),
        }
        for d in docs
    ]


@app.get("/api/documents/{id}")
def document_detail(id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = db.get(Document, id)
    if not doc:
        raise HTTPException(404, "Document not found.")
    site_allowed(user, doc.site)
    return {
        "id": doc.id,
        "title": doc.title,
        "version": doc.version,
        "pages": doc.pages,
        "site": doc.site,
        "site_id": doc.site_id,
        "kind": doc.kind,
        "checksum": doc.checksum,
        "filename": doc.filename,
        **original_metadata(db,doc),
    }


@app.post("/api/documents/upload", status_code=201)
async def upload(
    request: Request,
    file: UploadFile = File(...),
    site: str = Form(...),
    kind: str = Form("All equipment"),
    title: str = Form(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    allow(user, "engineer", "admin")
    site_allowed(user, site)
    if kind not in ("All equipment", "Pump", "Compressor", "Motor", "Turbine"):
        raise HTTPException(422, "Choose a supported equipment applicability.")
    if not 3 <= len(title.strip()) <= 200:
        raise HTTPException(422, "Document title must have 3 to 200 characters.")
    data = await file.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "The maximum document size is 10 MB.")
    checksum = hashlib.sha256(data).hexdigest()
    filename = original_filename(file.filename)
    body = {"checksum": checksum, "site": site, "kind": kind, "title": title.strip(), "archive_original": True, "filename": filename}
    key, h, old = idempotent(db, request, user, body)
    if old:
        return old
    try:
        if filename.lower().endswith(".pdf") and data.startswith(b"%PDF"):
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise ValueError("Encrypted PDFs are not supported.")
            if len(reader.pages) > 150:
                raise ValueError("Use a document with at most 150 pages.")
            pages = [(p.extract_text() or "")[:30000] for p in reader.pages]
        elif filename.lower().endswith((".txt", ".md")):
            pages = [data.decode("utf-8")[:200000]]
        else:
            raise ValueError("Upload a text-based PDF or UTF-8 text file.")
    except Exception as exc:
        raise HTTPException(
            422, str(exc) if isinstance(exc, ValueError) else "The document could not be parsed."
        )
    if sum(len(p.strip()) for p in pages) < 30:
        raise HTTPException(
            422, "No usable text was found. Scanned files need OCR before uploading."
        )
    doc = Document(
        title=title.strip(), filename=filename, site=site, kind=kind, pages=pages, checksum=checksum
    )
    db.add(doc)
    db.flush()
    media_type = "application/pdf" if filename.lower().endswith(".pdf") else "text/markdown" if filename.lower().endswith(".md") else "text/plain"
    db.add(DocumentOriginal(document_id=doc.id,content=data,checksum=checksum,byte_size=len(data),media_type=media_type))
    audit(db, user, site, "Document indexed", doc.title, "Original archived; SHA-256 "+checksum)
    return finish(db, key, h, {"id": doc.id, "title": doc.title, "page_count": len(pages), "original_archived": True, "original_bytes": len(data)})


@app.post("/api/knowledge/ask")
def ask(body: Question, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.site:
        site_allowed(user, body.site)
    docs = list(
        db.scalars(
            select(Document).where(Document.site.in_([body.site] if body.site else user.sites))
        )
    )
    evidence = search_documents(docs, body.question, 4, body.kind)
    # Extractive local answers retain exact passages, with no external provider call.
    if not evidence:
        return {
            "answer": "I could not find enough applicable evidence in your authorized documents. Add a relevant procedure or clarify the equipment and question.",
            "evidence": [],
            "status": "insufficient_evidence",
            "engine": "Local extractive retrieval",
        }
    return {
        "answer": "The following passages are the closest matches in your authorized knowledge base. Review their applicability before using them in a maintenance decision.",
        "evidence": evidence,
        "status": "evidence_found",
        "engine": "Lexical + hashed-vector retrieval · not a generative LLM",
    }


@app.get("/api/investigations")
def investigations(
    site: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    ids = [a.id for a in accessible_assets(db, user, site)]
    return [
        inv_json(db, i)
        for i in db.scalars(
            select(Investigation)
            .where(Investigation.asset_id.in_(ids))
            .order_by(Investigation.created.desc())
        )
    ]


@app.post("/api/investigations", status_code=201)
def investigate(
    body: Investigate,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    allow(user, "engineer", "planner", "admin")
    a = asset_for(db, user, body.asset_id)
    key, h, old = idempotent(db, request, user, body.model_dump())
    if old:
        return old
    r = latest(db, a.id)
    if not r or r.quality != "good" or now() - r.timestamp > 3600:
        raise HTTPException(
            409,
            "Fresh, good-quality telemetry is required. Replay or ingest a current sample first.",
        )
    docs = list(db.scalars(select(Document).where(Document.site == a.site)))
    payload = make_investigation(a, r, docs)
    inv = Investigation(
        asset_id=a.id,
        creator_id=user.id,
        title=body.title or f"Condition review · {a.tag}",
        payload=payload,
        payload_hash=payload_hash(payload),
    )
    db.add(inv)
    db.flush()
    audit(db, user, a.site, "Investigation prepared", a.tag, "Version 1 · local evidence workflow")
    db.add(
        RecommendationRevision(
            investigation_id=inv.id,
            version=1,
            actor_id=user.id,
            payload=payload,
            payload_hash=inv.payload_hash,
        )
    )
    return finish(db, key, h, inv_json(db, inv))


@app.get("/api/investigations/{id}")
def investigation_detail(
    id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    inv, a = investigation_for(db, user, id)
    return inv_json(db, inv)


@app.get("/api/investigations/{id}/history")
def investigation_history(
    id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    inv, a = investigation_for(db, user, id)
    return [
        {
            "version": r.version,
            "payload": r.payload,
            "payload_hash": r.payload_hash,
            "actor_id": r.actor_id,
            "created": r.created,
        }
        for r in db.scalars(
            select(RecommendationRevision)
            .where(RecommendationRevision.investigation_id == id)
            .order_by(RecommendationRevision.version)
        )
    ]


@app.patch("/api/investigations/{id}")
def edit_draft(
    id: str,
    body: DraftEdit,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    allow(user, "engineer", "planner", "admin")
    inv, a = investigation_for(db, user, id)
    key, h, old = idempotent(db, request, user, body.model_dump())
    if old:
        return old
    check_version(inv.version, body.expected_version)
    if inv.state == "dispatched":
        raise HTTPException(409, "An already submitted recommendation cannot be edited.")
    payload = {**inv.payload, "recommendation": body.recommendation, "checklist": body.checklist}
    db.add(
        RecommendationRevision(
            investigation_id=inv.id,
            version=inv.version + 1,
            actor_id=user.id,
            payload=payload,
            payload_hash=payload_hash(payload),
        )
    )
    atomic_version(
        db,
        Investigation,
        id,
        inv.version,
        {
            "payload": payload,
            "payload_hash": payload_hash(payload),
            "creator_id": user.id,
            "state": "awaiting_review",
            "approved_by": None,
            "approved_hash": None,
            "approved_until": None,
            "decision_reason": "",
        },
    )
    audit(db, user, a.site, "Recommendation revised", a.tag, "Previous approval invalidated")
    db.flush()
    db.refresh(inv)
    return finish(db, key, h, inv_json(db, inv))


@app.post("/api/investigations/{id}/decision")
def decide(
    id: str,
    body: Decision,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    allow(user, "approver", "admin")
    inv, a = investigation_for(db, user, id)
    key, h, old = idempotent(db, request, user, body.model_dump())
    if old:
        return old
    check_version(inv.version, body.expected_version)
    if inv.state != "awaiting_review":
        raise HTTPException(409, "Only a recommendation awaiting review can be decided.")
    if inv.creator_id == user.id:
        raise HTTPException(403, "A different authorized person must review this recommendation.")
    if body.decision == "approve" and not inv.payload.get("evidence"):
        raise HTTPException(409, "Applicable document evidence is required before approval.")
    vals = {
        "state": "approved" if body.decision == "approve" else "rejected",
        "decision_reason": body.reason,
        "approved_by": user.id if body.decision == "approve" else None,
        "approved_hash": inv.payload_hash if body.decision == "approve" else None,
        "approved_until": now() + 86400 if body.decision == "approve" else None,
    }
    atomic_version(db, Investigation, id, inv.version, vals)
    audit(
        db,
        user,
        a.site,
        "Recommendation " + vals["state"],
        a.tag,
        f"Version {body.expected_version}; hash {inv.payload_hash}; {body.reason}",
    )
    db.flush()
    db.refresh(inv)
    return finish(db, key, h, inv_json(db, inv))


@app.get("/api/work-orders")
def work_orders(
    site: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    ids = [a.id for a in accessible_assets(db, user, site)]
    return [
        order_json(db, o)
        for o in db.scalars(
            select(WorkOrder).where(WorkOrder.asset_id.in_(ids)).order_by(WorkOrder.created.desc())
        )
    ]


@app.post("/api/work-orders", status_code=201)
def create_order(
    body: OrderCreate,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    allow(user, "planner", "admin")
    inv, a = investigation_for(db, user, body.investigation_id)
    key, h, old = idempotent(db, request, user, body.model_dump())
    if old:
        return old
    check_version(inv.version, body.expected_version)
    if (
        inv.state != "approved"
        or inv.approved_hash != inv.payload_hash
        or not inv.approved_until
        or inv.approved_until < now()
    ):
        raise HTTPException(409, "A current approval for this exact recommendation is required.")
    atomic_version(db, Investigation, inv.id, inv.version, {"state": "dispatched"})
    ref = f"WO-{datetime.now(timezone.utc).year}-{secrets.token_hex(3).upper()}"
    order = WorkOrder(
        reference=ref,
        asset_id=a.id,
        investigation_id=inv.id,
        title=inv.payload["recommendation"][:240],
        priority=inv.payload["priority"],
        assignee=body.assignee,
        due_date=body.due_date,
    )
    db.add(order)
    db.flush()
    audit(db, user, a.site, "Work order planned", order.reference)
    return finish(db, key, h, order_json(db, order))


@app.post("/api/work-orders/{id}/dispatch")
def dispatch(
    id: str,
    body: Dispatch,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    allow(user, "planner", "admin")
    order, a = order_for(db, user, id)
    key, h, old = idempotent(db, request, user, body.model_dump())
    if old:
        return old
    check_version(order.version, body.expected_version)
    if order.status != "planned":
        raise HTTPException(409, "Only a planned order can be dispatched.")
    inv = db.get(Investigation, order.investigation_id)
    if (
        not inv.approved_until
        or inv.approved_until < now()
        or inv.approved_hash != inv.payload_hash
    ):
        raise HTTPException(409, "The approval is expired or no longer matches.")
    # Simulator persists acceptance before returning an intentional uncertain result.
    external = db.get(ExternalOrder, order.id)
    if not external:
        external = ExternalOrder(command_id=order.id, external_ref=f"SIM-{order.reference}")
        db.add(external)
    atomic_version(
        db,
        WorkOrder,
        id,
        order.version,
        {
            "status": "reconciling" if body.simulate_timeout else "in_progress",
            "external_ref": None if body.simulate_timeout else external.external_ref,
        },
    )
    audit(
        db,
        user,
        a.site,
        "CMMS outcome uncertain" if body.simulate_timeout else "Work order dispatched",
        order.reference,
        "Local CMMS simulator",
    )
    db.flush()
    db.refresh(order)
    return finish(db, key, h, order_json(db, order))


@app.post("/api/work-orders/{id}/reconcile")
def reconcile(
    id: str,
    body: VersionCommand,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    allow(user, "planner", "admin")
    order, a = order_for(db, user, id)
    key, h, old = idempotent(db, request, user, body.model_dump())
    if old:
        return old
    check_version(order.version, body.expected_version)
    if order.status != "reconciling":
        raise HTTPException(409, "This order does not need reconciliation.")
    external = db.get(ExternalOrder, id)
    if not external:
        raise HTTPException(409, "No confirmed external result. Manual review is required.")
    atomic_version(
        db,
        WorkOrder,
        id,
        order.version,
        {"status": "in_progress", "external_ref": external.external_ref},
    )
    audit(
        db,
        user,
        a.site,
        "Work order reconciled",
        order.reference,
        "Existing simulator order found; no duplicate created",
    )
    db.flush()
    db.refresh(order)
    return finish(db, key, h, order_json(db, order))


@app.post("/api/work-orders/{id}/transition")
def transition_order(
    id: str,
    body: OrderTransition,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    allow(user, "planner", "technician", "admin")
    order, a = order_for(db, user, id)
    key, h, old = idempotent(db, request, user, body.model_dump())
    if old:
        return old
    check_version(order.version, body.expected_version)
    if body.status == "completed":
        if order.status != "in_progress" or len(body.outcome.strip()) < 10:
            raise HTTPException(
                409, "Complete an in-progress order with at least 10 characters of actual findings."
            )
    elif body.status == "cancelled":
        allow(user, "planner", "admin")
        if order.status not in ("planned", "in_progress") or len(body.outcome.strip()) < 5:
            raise HTTPException(409, "Cancellation needs a reason and a known order state.")
        ext = db.get(ExternalOrder, id)
        if ext:
            ext.state = "cancelled"
    else:
        raise HTTPException(409, "Use dispatch to start planned work.")
    atomic_version(
        db, WorkOrder, id, order.version, {"status": body.status, "outcome": body.outcome}
    )
    audit(db, user, a.site, "Work order " + body.status, order.reference, body.outcome)
    db.flush()
    db.refresh(order)
    return finish(db, key, h, order_json(db, order))


@app.get("/api/activity")
def activity(
    site: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    if site:
        site_allowed(user, site)
    return [
        {
            k: getattr(row, k)
            for k in ["id", "actor", "action", "target", "details", "created", "site", "site_id"]
        }
        for row in db.scalars(
            select(Audit)
            .where(Audit.site.in_([site] if site else user.sites))
            .order_by(Audit.created.desc())
            .limit(200)
        )
    ]


@app.get("/api/model")
def model(user: User = Depends(current_user)):
    return model_metrics()


@app.get("/api/operations")
def operations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    assets = accessible_assets(db, user)
    ids = [a.id for a in assets]
    count = db.scalar(select(func.count(Reading.id)).where(Reading.asset_id.in_(ids))) or 0
    return {
        "services": [
            {"name": "API service", "status": "operational", "detail": "FastAPI · local runtime"},
            {
                "name": "Database",
                "status": "operational",
                "detail": (
                    "SQLite · local persistence"
                    if DATABASE_URL.startswith("sqlite")
                    else "PostgreSQL"
                ),
            },
            {
                "name": "Anomaly detection",
                "status": "operational",
                "detail": "Isolation Forest · synthetic baseline",
            },
            {
                "name": "Knowledge retrieval",
                "status": "operational",
                "detail": "Lexical + hashed vectors",
            },
            {
                "name": "CMMS integration",
                "status": "simulation",
                "detail": "Persistent local simulator",
            },
        ],
        "snapshots": count,
        "api_p95_ms": round(float(np.percentile(REQUEST_TIMES, 95)), 1) if REQUEST_TIMES else 0,
        "requests_measured": len(REQUEST_TIMES),
        "model": model_metrics(),
        "limitations": [
            "No real SCADA/PLC control connection",
            "No vendor CMMS connection",
            "No OCR for scanned PDFs",
            "No certified failure probability or RUL",
            "No OIDC/SSO in this local reference build",
        ],
    }


@app.get("/api/preferences")
def prefs(user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.get(Preference, user.id)
    return row.values if row else Preferences().model_dump()


@app.put("/api/preferences")
def set_prefs(body: Preferences, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.get(Preference, user.id)
    if row:
        row.values = body.model_dump()
    else:
        db.add(Preference(user_id=user.id, values=body.model_dump()))
    db.commit()
    return body.model_dump()


@app.get("/api/export/assets.csv")
def export(user: User = Depends(current_user), db: Session = Depends(get_db)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "Tag",
            "Name",
            "Type",
            "Site",
            "Condition index",
            "Status",
            "Vibration mm/s",
            "Temperature C",
            "Source",
        ]
    )
    for a in accessible_assets(db, user):
        row = asset_json(db, a)
        r = row["reading"] or {}
        # Neutralize spreadsheet formula injection for user-provided labels.
        vals = [
            a.tag,
            a.name,
            a.kind,
            a.site,
            row["health"],
            row["status"],
            r.get("vibration"),
            r.get("temperature"),
            row["source"],
        ]
        w.writerow(
            [
                "'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v
                for v in vals
            ]
        )
    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="sentinel-assets.csv"'},
    )


app.include_router(create_router(accessible_assets, asset_for, asset_json, reading_json, latest, idempotent, finish))
app.include_router(create_sensor_router(accessible_assets, asset_for, latest))
app.include_router(create_event_router(asset_for, idempotent, finish))
app.include_router(create_projection_router(asset_for, latest, check_episode, idempotent, finish))
app.include_router(create_quarantine_router(asset_for, idempotent, finish))
app.include_router(create_recovery_router(idempotent, finish))
app.include_router(create_original_router())
app.include_router(create_gateway_router(accessible_assets, asset_for, idempotent, finish))
app.include_router(create_site_router())
app.include_router(create_foundation_router(idempotent, finish, asset_for))
app.include_router(create_team_router())
app.include_router(create_account_router())
app.include_router(create_mfa_router(user_json))
app.include_router(create_condition_rule_router(asset_for, idempotent, finish))
app.include_router(create_live_rule_router(asset_for, idempotent, finish))
app.include_router(create_rule_review_router(asset_for, idempotent, finish))
app.include_router(create_rule_inbox_router())
app.include_router(create_rule_assignment_router(asset_for, idempotent, finish))
app.include_router(create_match_investigation_router(asset_for, idempotent, finish, inv_json, latest))
app.include_router(create_maintenance_window_router(asset_for, idempotent, finish))
app.include_router(create_maintenance_control_router(asset_for, idempotent, finish))
app.include_router(create_notification_plan_router(asset_for, idempotent, finish))
app.include_router(create_notification_review_router(asset_for, idempotent, finish))

DIST = Path(__file__).resolve().parents[1] / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="static-assets")

    @app.get("/sentinel.svg", include_in_schema=False)
    def favicon():
        return FileResponse(DIST / "sentinel.svg")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "API route not found.")
        return FileResponse(DIST / "index.html")
