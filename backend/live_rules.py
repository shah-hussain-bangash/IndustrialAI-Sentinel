"""Exact-revision rule activation. Local snapshot processing, no outbound notifications."""
import math
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .database import ConditionRule, ConditionRuleRevision, ConditionRuleDeployment, ConditionRuleMatch, Reading, Audit, Asset, User, now, MaintenanceWindowSuppression
from .maintenance_policy import intervals, suppression_for, crosses_window
from .security import allow, current_user, get_db
from .rule_reviews import current_review, review_json


def status_json(row):
    return {"state": row.state if row else "inactive", "version": row.version if row else 0,
            "rule_version": row.rule_version if row else None,
            "activated_at": row.activated_at if row else None,
            "last_evaluated_at": row.evaluated_at if row else None}


def close_matches(db, rule_id, at, reason, asset):
    for match in db.scalars(select(ConditionRuleMatch).where(ConditionRuleMatch.rule_id == rule_id, ConditionRuleMatch.state == "active")):
        match.state = reason; match.ended_at = at
        db.add(Audit(site=asset.site, actor="Condition rule evaluator", action="Rule match " + reason, target=asset.tag,
                     details=f"Rule {rule_id}; revision {match.rule_version}; match {match.id}. No maintenance action or notification."))


def process_snapshot(db, asset, reading):
    db.flush()
    db.execute(update(Asset).where(Asset.id == asset.id).values(version=Asset.version))
    windows = intervals(db, asset.id)
    suppressed_by = suppression_for(windows, reading.timestamp, now())
    deployments = list(db.scalars(select(ConditionRuleDeployment).join(ConditionRule, ConditionRule.id == ConditionRuleDeployment.rule_id)
                                 .where(ConditionRule.asset_id == asset.id, ConditionRuleDeployment.state == "active")))
    for row in deployments:
        if reading.timestamp <= max(row.last_timestamp, row.activated_at):
            continue
        locked = db.execute(update(ConditionRuleDeployment).where(ConditionRuleDeployment.rule_id == row.rule_id,
                            ConditionRuleDeployment.evaluation_version == row.evaluation_version,
                            ConditionRuleDeployment.state == "active")
                            .values(evaluation_version=ConditionRuleDeployment.evaluation_version + 1)
                            .execution_options(synchronize_session=False))
        if locked.rowcount != 1:
            raise HTTPException(409, "Rule evaluation changed concurrently. Retry the same batch request.")
        db.refresh(row)
        config = db.get(ConditionRuleRevision, (row.rule_id, row.rule_version)).settings
        if crosses_window(windows, row.last_timestamp, reading.timestamp):
            row.candidate_since = None
        value = getattr(reading, config["channel"])
        if row.last_timestamp and reading.timestamp - row.last_timestamp > config["maximum_gap_seconds"]:
            close_matches(db, row.rule_id, row.last_timestamp, "data_gap", asset)
            row.candidate_since = None
        if reading.quality != "good" or not math.isfinite(value):
            close_matches(db, row.rule_id, row.last_timestamp or reading.timestamp, "invalid_sample", asset)
            row.candidate_since = None
        else:
            active = db.scalar(select(ConditionRuleMatch).where(ConditionRuleMatch.rule_id == row.rule_id, ConditionRuleMatch.state == "active"))
            if active:
                if value <= config["threshold"] - config["hysteresis"]:
                    close_matches(db, row.rule_id, reading.timestamp, "cleared", asset)
                    row.candidate_since = None
            elif suppressed_by:
                row.candidate_since = None
                if value > config["threshold"]:
                    db.add(MaintenanceWindowSuppression(rule_id=row.rule_id, rule_version=row.rule_version,
                        reading_id=reading.id, draft_id=suppressed_by, control_version=1, observed_at=reading.timestamp))
            elif value > config["threshold"]:
                if row.candidate_since is None:
                    row.candidate_since = reading.timestamp
                if reading.timestamp - row.candidate_since >= config["persistence_seconds"]:
                    match = ConditionRuleMatch(rule_id=row.rule_id, rule_version=row.rule_version, state="active",
                                               started_at=row.candidate_since, triggered_at=reading.timestamp, trigger_reading_id=reading.id)
                    db.add(match); db.flush()
                    db.add(Audit(site=asset.site, actor="Condition rule evaluator", action="Rule match triggered", target=asset.tag,
                                 details=f"Rule {row.rule_id}; revision {row.rule_version}; match {match.id}; reading {reading.id}. Review signal evidence; no physical diagnosis."))
            else:
                row.candidate_since = None
        row.last_timestamp = reading.timestamp
        row.evaluated_at = reading.timestamp
        db.flush()


class RuleControl(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["activate", "pause"]
    expected_version: int = Field(ge=0)
    expected_rule_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=500)
    confirmed: Literal[True]

    @field_validator("reason")
    @classmethod
    def reason_text(cls, value):
        if not value.strip() or any(ord(c) < 32 for c in value):
            raise ValueError("Provide a reason without control characters.")
        return value.strip()


def create_live_rule_router(asset_for, idempotent, finish):
    router = APIRouter(prefix="/api/condition-rules", tags=["Controlled condition rule activation"])

    def rule_for(db, user, rule_id):
        rule = db.get(ConditionRule, rule_id)
        if rule is None: raise HTTPException(404, "Rule not found.")
        return rule, asset_for(db, user, rule.asset_id)

    @router.get("/drafts/{rule_id}/deployment")
    def deployment(rule_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
        allow(user, "engineer", "admin")
        rule, asset = rule_for(db, user, rule_id)
        result = status_json(db.get(ConditionRuleDeployment, rule_id))
        revision = db.get(ConditionRuleRevision, (rule_id, result["rule_version"])) if result["rule_version"] else None
        return {**result, "latest_rule_version": rule.version, "settings": revision.settings if revision else None}

    @router.post("/drafts/{rule_id}/control")
    def control(rule_id: str, body: RuleControl, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
        allow(user, "admin")
        rule, asset = rule_for(db, user, rule_id)
        key, digest, receipt = idempotent(db, request, user, body.model_dump())
        if receipt is not None: return receipt
        # Serialize control operations per asset, including the active-rule bound.
        db.execute(update(Asset).where(Asset.id == asset.id).values(version=Asset.version))
        # Lock the exact draft head against concurrent revision saves.
        locked = db.execute(update(ConditionRule).where(ConditionRule.id == rule.id, ConditionRule.version == body.expected_rule_version)
                            .values(version=ConditionRule.version).execution_options(synchronize_session=False))
        if locked.rowcount != 1: raise HTTPException(409, "The saved revision changed. Reload before activating or pausing.")
        row = db.scalar(select(ConditionRuleDeployment).where(ConditionRuleDeployment.rule_id == rule_id).with_for_update())
        if (row.version if row else 0) != body.expected_version:
            raise HTTPException(409, "Activation state changed. Reload before continuing.")
        if body.action == "pause" and (row is None or row.state != "active"):
            raise HTTPException(409, "This rule is not active.")
        if body.action == "activate" and row and row.state == "active" and row.rule_version == body.expected_rule_version:
            raise HTTPException(409, "This exact revision is already active.")
        if body.action == "activate":
            count = db.scalar(select(func.count()).select_from(ConditionRuleDeployment).join(ConditionRule, ConditionRule.id == ConditionRuleDeployment.rule_id)
                              .where(ConditionRule.asset_id == asset.id, ConditionRuleDeployment.state == "active"))
            if count >= 20 and (row is None or row.state != "active"):
                raise HTTPException(422, "Pause another rule first; this local build supports 20 active rules per equipment item.")
        clock = now()
        close_matches(db, rule_id, clock, "paused" if body.action == "pause" else "replaced", asset)
        watermark = db.scalar(select(func.max(Reading.timestamp)).where(Reading.asset_id == asset.id)) or 0
        if row is None:
            row = ConditionRuleDeployment(rule_id=rule_id, rule_version=body.expected_rule_version, state="active",
                                          version=1, evaluation_version=1, activated_at=clock, last_timestamp=watermark, candidate_since=None)
            db.add(row)
        else:
            row.version += 1; row.evaluation_version += 1; row.candidate_since = None
            row.state = "paused" if body.action == "pause" else "active"
            if body.action == "activate":
                row.rule_version = body.expected_rule_version; row.activated_at = clock; row.last_timestamp = watermark; row.evaluated_at = None
        db.add(Audit(site=asset.site, actor=user.name, action="Condition rule " + ("activated" if body.action == "activate" else "paused"), target=asset.tag,
                     details=f"Rule {rule_id}; revision {row.rule_version}. Reason: {body.reason}. New snapshots only; no outbound notifications."))
        try:
            db.flush()
            return finish(db, key, digest, status_json(row))
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Rule state changed concurrently. Reload before retrying.") from None

    @router.get("/activity")
    def activity(asset_id: str = Query(min_length=1, max_length=36), user: User = Depends(current_user), db: Session = Depends(get_db)):
        allow(user, "engineer", "admin")
        asset_for(db, user, asset_id)
        rows = list(db.execute(select(ConditionRuleMatch, ConditionRuleRevision)
                               .join(ConditionRule, ConditionRule.id == ConditionRuleMatch.rule_id)
                               .join(ConditionRuleRevision, (ConditionRuleRevision.rule_id == ConditionRuleMatch.rule_id) &
                                     (ConditionRuleRevision.version == ConditionRuleMatch.rule_version))
                               .where(ConditionRule.asset_id == asset_id)
                               .order_by(ConditionRuleMatch.created.desc(), ConditionRuleMatch.id).limit(101)))
        return {"items": [{"id": m.id, "name": revision.name, "rule_version": m.rule_version, "state": m.state,
                           "started_at": m.started_at, "triggered_at": m.triggered_at, "ended_at": m.ended_at,
                           "trigger_reading_id": m.trigger_reading_id, "review": review_json(current_review(db, m.id))} for m, revision in rows[:100]],
                "truncated": len(rows) > 100,
                "boundary": "Snapshot-driven local matches only. An active match describes the last processed snapshot, not guaranteed current equipment condition. No email, external dispatch or maintenance action."}

    return router
