"""Deterministic, entirely synthetic demonstration data."""

import hashlib
import json
import math
import os
import numpy as np
from sqlalchemy import select
from .database import (
    Base,
    engine,
    SessionLocal,
    User,
    Asset,
    Reading,
    Episode,
    Document,
    Investigation,
    WorkOrder,
    RecommendationRevision,
    Audit,
    now,
)
from .security import password_hash, DEMO_PASSWORD, DEMO_ENABLED
from .intelligence import make_investigation

SITES = ["Ruwais Energy Complex", "Habshan Processing Hub"]


def payload_hash(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def initialize():
    # For local demo convenience only; managed deployments use Alembic.
    if os.getenv("AUTO_CREATE_SCHEMA", "true").lower() == "true":
        Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(User).limit(1)):
            return
        if not DEMO_ENABLED:
            email, password = os.getenv("INITIAL_ADMIN_EMAIL"), os.getenv("INITIAL_ADMIN_PASSWORD")
            if not email or not password or len(password) < 12:
                raise RuntimeError(
                    "With DEMO_MODE=false set INITIAL_ADMIN_EMAIL and a password of at least 12 characters."
                )
            db.add(
                User(
                    email=email,
                    name="Workspace administrator",
                    role="admin",
                    password_hash=password_hash(password),
                    sites=SITES,
                )
            )
            db.commit()
            return
        users = []
        for email, name, role, sites in [
            ("engineer@sentinel.local", "Alex Morgan", "engineer", SITES),
            ("approver@sentinel.local", "Samira Ahmed", "approver", SITES),
            ("planner@sentinel.local", "Omar Khalid", "planner", SITES),
            ("technician@sentinel.local", "Riya Patel", "technician", SITES),
            ("admin@sentinel.local", "Workspace Admin", "admin", SITES),
            ("restricted@sentinel.local", "Habshan Observer", "observer", [SITES[1]]),
        ]:
            user = User(
                email=email,
                name=name,
                role=role,
                password_hash=password_hash(DEMO_PASSWORD),
                sites=sites,
            )
            db.add(user)
            users.append(user)
        db.flush()
        specs = [
            ("P-101", "Crude transfer pump", "Pump", SITES[0], "Train 04 · Transfer", 6.9, 86),
            (
                "C-202",
                "Gas injection compressor",
                "Compressor",
                SITES[0],
                "Train 02 · Compression",
                4.4,
                79,
            ),
            ("P-103", "Cooling water pump", "Pump", SITES[0], "Utilities · Loop A", 2.1, 64),
            ("M-301", "Main drive motor", "Motor", SITES[0], "Train 04 · Drive", 1.8, 62),
            ("P-106", "Condensate export pump", "Pump", SITES[0], "Export · Terminal", 2.4, 68),
            (
                "T-401",
                "Steam turbine generator",
                "Turbine",
                SITES[0],
                "Utilities · Generation",
                1.9,
                66,
            ),
            (
                "C-205",
                "Instrument air compressor",
                "Compressor",
                SITES[0],
                "Utilities · Air",
                2.3,
                67,
            ),
            ("P-108", "Boiler feedwater pump", "Pump", SITES[0], "Utilities · Boiler", 3.5, 76),
            ("M-304", "Cooling tower motor", "Motor", SITES[0], "Utilities · Tower", 1.6, 59),
            ("P-201", "Process circulation pump", "Pump", SITES[1], "Unit 02 · Process", 2.2, 66),
            ("C-302", "Booster compressor", "Compressor", SITES[1], "Unit 03 · Boost", 2.5, 71),
            ("P-204", "Seal water pump", "Pump", SITES[1], "Unit 02 · Seals", 1.7, 61),
        ]
        rng = np.random.default_rng(19)
        assets = []
        lasts = []
        t = now()
        for index, (tag, name, kind, site, location, vib, temp) in enumerate(specs):
            asset = Asset(
                tag=tag,
                name=name,
                kind=kind,
                site=site,
                location=location,
                criticality="Critical" if index in (0, 1, 5) else "High" if index % 3 else "Medium",
            )
            db.add(asset)
            db.flush()
            assets.append(asset)
            readings = []
            for step in range(120):
                progress = step / 119
                v = 2.2 + (vib - 2.2) * progress if index in (0, 1, 7) else vib
                reading = Reading(
                    asset_id=asset.id,
                    timestamp=t - (119 - step) * 300,
                    vibration=round(
                        max(0.1, v + math.sin(step * 0.25) * 0.13 + rng.normal(0, 0.09)), 3
                    ),
                    temperature=round(temp + math.sin(step * 0.17) * 1.5 + rng.normal(0, 0.5), 2),
                    pressure=round(
                        5.2 + rng.normal(0, 0.16) - (0.5 * progress if index == 0 else 0), 3
                    ),
                    flow=round(120 + rng.normal(0, 4) - (15 * progress if index == 0 else 0), 2),
                )
                readings.append(reading)
            db.add_all(readings)
            lasts.append(readings[-1])
            if index in (0, 1, 7):
                db.add(
                    Episode(
                        asset_id=asset.id,
                        title=(
                            "Elevated vibration trend"
                            if index != 7
                            else "Temperature above baseline"
                        ),
                        severity="critical" if index == 0 else "warning",
                        created=t - (index + 1) * 600,
                    )
                )
        db.flush()
        for site in SITES:
            manuals = [
                (
                    "Pump inspection procedure",
                    "Pump",
                    [
                        "SYNTHETIC DEMONSTRATION PROCEDURE. This is not an OEM manual. Pump vibration monitoring: verify sensor mounting, units and operating state before diagnosis. Compare trends at comparable flow and pressure. Elevated vibration can reflect several conditions and does not alone confirm a bearing fault.",
                        "Pump inspection checklist: a qualified technician should review lubrication records, alignment history and bearing condition using established site procedures. Confirm equipment applicability and approved isolation requirements before physical inspection. Record actual observations and escalate unclear findings to the reliability engineer.",
                    ],
                ),
                (
                    "Rotating equipment condition guide",
                    "All equipment",
                    [
                        "SYNTHETIC DEMONSTRATION GUIDE. Rotating equipment condition monitoring combines vibration, temperature, pressure and flow with maintenance history. Missing or stuck sensor values require data-quality review. Inspect trend changes against operating load before making a maintenance recommendation.",
                        "For compressors, motors and turbines: review mounting, lubrication, alignment and operating conditions with a qualified domain reviewer. Draft a work order only after checking relevant evidence. An authorized approver must review the exact maintenance recommendation. This document provides no certified thresholds or safety instructions.",
                    ],
                ),
                (
                    "Maintenance approval and recording",
                    "All equipment",
                    [
                        "SYNTHETIC DEMONSTRATION POLICY. The draft creator cannot approve their own recommendation. Approval binds the current version and expires after 24 hours. A revised action requires a new review. Work order submission must be idempotent. Reconcile an uncertain result before retrying creation.",
                        "Technician findings are observations, not automatically the same as the initial hypothesis. Close a work order with actual inspection results. Keep the audit history of recommendation, approval, submission, completion and any cancellation.",
                    ],
                ),
            ]
            for title, kind, pages in manuals:
                doc = Document(
                    title=title,
                    filename=title.lower().replace(" ", "-") + ".txt",
                    site=site,
                    kind=kind,
                    pages=pages,
                    checksum=hashlib.sha256("\n".join(pages).encode()).hexdigest(),
                )
                db.add(doc)
        db.flush()
        docs = list(db.scalars(select(Document)))
        for i in range(5):
            ix = [0, 1, 2, 3, 7][i]
            asset = assets[ix]
            payload = make_investigation(
                asset, lasts[ix], [d for d in docs if d.site == asset.site]
            )
            inv = Investigation(
                asset_id=asset.id,
                creator_id=users[0].id,
                title=f"Condition review · {asset.tag}",
                payload=payload,
                payload_hash=payload_hash(payload),
                created=t - (i + 1) * 1800,
            )
            db.add(inv)
            db.flush()
            db.add(
                RecommendationRevision(
                    investigation_id=inv.id,
                    version=1,
                    actor_id=users[0].id,
                    payload=payload,
                    payload_hash=inv.payload_hash,
                )
            )
            if i:
                inv.state = "approved" if i == 1 else "dispatched"
                inv.approved_by = users[1].id
                inv.approved_hash = inv.payload_hash
                inv.approved_until = t + 86400
                if i >= 2:
                    db.add(
                        WorkOrder(
                            reference=f"WO-2026-{1040+i}",
                            asset_id=asset.id,
                            investigation_id=inv.id,
                            title=[
                                "",
                                "",
                                "Inspect coupling alignment",
                                "Review motor lubrication",
                                "Inspect pump operating condition",
                            ][i],
                            priority="High" if i == 4 else "Medium",
                            status=(
                                "in_progress" if i == 2 else "completed" if i == 3 else "planned"
                            ),
                            assignee="Riya Patel" if i != 4 else "Unassigned",
                            due_date=__import__("datetime")
                            .datetime.fromtimestamp(
                                t + (i - 2) * 86400, __import__("datetime").timezone.utc
                            )
                            .date()
                            .isoformat(),
                            external_ref=f"SIM-CMMS-{1040+i}" if i in (2, 3) else None,
                            outcome=(
                                "Synthetic seed record: inspection recorded for demonstration."
                                if i == 3
                                else ""
                            ),
                            created=t - i * 7200,
                        )
                    )
        for i, (action, target) in enumerate(
            [
                ("Workspace initialized", "Synthetic demonstration dataset"),
                ("Model evaluated", "Isolation Forest · synthetic holdout"),
                ("Document indexed", "Pump inspection procedure"),
                ("Investigation prepared", "P-101 · vibration trend"),
                ("Work order completed", "WO-2026-1043"),
                ("Sensor batch ingested", "Ruwais · 48 channels"),
            ]
        ):
            db.add(
                Audit(
                    site=SITES[0],
                    actor="System demo seed",
                    action=action,
                    target=target,
                    details="Synthetic seed activity",
                    created=t - i * 900,
                )
            )
        db.commit()
