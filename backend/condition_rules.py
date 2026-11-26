"""Historical rule previews and versioned drafts. Activation is a separate router."""
import math
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import Reading, User, ConditionRule, ConditionRuleRevision, Audit, now
from .security import allow, current_user, get_db


class RulePreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str = Field(min_length=1, max_length=36)
    channel: Literal["vibration", "temperature", "pressure", "flow"]
    threshold: float = Field(ge=-273.15, le=100000, allow_inf_nan=False)
    hysteresis: float = Field(default=0, ge=0, le=100000, allow_inf_nan=False)
    persistence_seconds: int = Field(default=30, ge=0, le=86400)
    maximum_gap_seconds: int = Field(default=300, ge=1, le=86400)


def evaluate(samples, channel, threshold, hysteresis, persistence_seconds, maximum_gap_seconds):
    """Trigger after continuous >threshold samples; clear at <=threshold-hysteresis.

    Bad quality, nonfinite values, duplicate times and long gaps break continuity.
    Recovery inside the hysteresis band retains an already active preview only.
    No interpolated values or assumed time beyond the final observation are used.
    """
    windows = []
    candidate = active = previous = None
    good = invalid = gaps = 0

    def close(at, reason):
        nonlocal candidate, active
        if active is not None:
            active.update(ended_at=at, end_reason=reason)
            windows.append(active)
        candidate = active = None

    for sample in samples:
        timestamp, value = sample["timestamp"], sample[channel]
        if previous is not None and (timestamp <= previous or timestamp - previous > maximum_gap_seconds):
            close(previous, "data_gap")
            gaps += 1
        if sample["quality"] != "good" or not math.isfinite(value):
            close(previous, "invalid_sample")
            invalid += 1
            previous = timestamp
            continue
        good += 1
        if active is not None:
            if value <= threshold - hysteresis:
                close(timestamp, "cleared")
        elif value > threshold:
            if candidate is None:
                candidate = timestamp
            if timestamp - candidate >= persistence_seconds:
                active = {"started_at": candidate, "triggered_at": timestamp, "ended_at": None, "end_reason": "end_of_history"}
        else:
            candidate = None
        previous = timestamp
    if active is not None:
        windows.append(active)
    return {"windows": windows, "trigger_count": len(windows), "good_samples": good,
            "invalid_samples": invalid, "continuity_breaks": gaps,
            "active_at_last_sample": active is not None,
            "pending_since": candidate if active is None else None}


class DraftCreate(RulePreview):
    name: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("name", "reason")
    @classmethod
    def clean_text(cls, value):
        if not value.strip() or any(ord(c) < 32 for c in value):
            raise ValueError("Provide text without control characters.")
        return value.strip()


class DraftUpdate(DraftCreate):
    expected_version: int = Field(ge=1)


def revision_json(row):
    return {"version": row.version, "name": row.name, "settings": row.settings,
            "reason": row.reason, "actor_name": row.actor_name, "created": row.created}


def create_condition_rule_router(asset_for, idempotent, finish):
    router = APIRouter(prefix="/api/condition-rules", tags=["Condition rule preview"])

    def permitted(user):
        allow(user, "engineer", "admin")

    def rule_for(db, user, rule_id):
        rule = db.get(ConditionRule, rule_id)
        if rule is None:
            raise HTTPException(404, "Rule draft not found.")
        asset_for(db, user, rule.asset_id)
        return rule

    def describe(db, rule):
        return {"id": rule.id, "asset_id": rule.asset_id, "state": "draft", "active": False,
                **revision_json(db.get(ConditionRuleRevision, (rule.id, rule.version)))}

    def write_revision(db, user, asset, rule, body):
        settings = {key: getattr(body, key) for key in RulePreview.model_fields}
        db.add(ConditionRuleRevision(rule_id=rule.id, version=rule.version, name=body.name,
                                   settings=settings, reason=body.reason, actor_id=user.id,
                                   actor_name=user.name, created=now()))
        db.add(Audit(site=asset.site, actor=user.name, action="Condition rule draft saved", target=asset.tag,
                     details=f"Rule {rule.id}; version {rule.version}; inactive draft. Reason: {body.reason}"))
        db.flush()

    def committed(db, key, digest, result):
        try:
            return finish(db, key, digest, result)
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Another request saved this change. Reload drafts before retrying.") from None

    @router.get("/drafts")
    def listing(asset_id: str = Query(min_length=1, max_length=36),
                user: User = Depends(current_user), db: Session = Depends(get_db)):
        permitted(user)
        asset_for(db, user, asset_id)
        rows = list(db.scalars(select(ConditionRule).where(ConditionRule.asset_id == asset_id)
                               .order_by(ConditionRule.created.desc(), ConditionRule.id).limit(101)))
        return {"items": [describe(db, row) for row in rows[:100]], "truncated": len(rows) > 100,
                "boundary": "Saving a draft does not change activation. See the separate deployment state for the running revision."}

    @router.post("/drafts", status_code=201)
    def create(body: DraftCreate, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
        permitted(user)
        asset = asset_for(db, user, body.asset_id)
        key, digest, receipt = idempotent(db, request, user, body.model_dump())
        if receipt is not None:
            return receipt
        rule = ConditionRule(asset_id=asset.id, version=1)
        db.add(rule); db.flush()
        write_revision(db, user, asset, rule, body)
        return committed(db, key, digest, describe(db, rule))

    @router.post("/drafts/{rule_id}")
    def revise(rule_id: str, body: DraftUpdate, request: Request,
               user: User = Depends(current_user), db: Session = Depends(get_db)):
        permitted(user)
        rule = rule_for(db, user, rule_id)
        if body.asset_id != rule.asset_id:
            raise HTTPException(422, "A rule cannot be moved to different equipment. Create a new draft.")
        key, digest, receipt = idempotent(db, request, user, body.model_dump())
        if receipt is not None:
            return receipt
        changed = db.execute(update(ConditionRule).where(ConditionRule.id == rule.id,
                             ConditionRule.version == body.expected_version)
                             .values(version=ConditionRule.version + 1).execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            raise HTTPException(409, "This draft changed. Reload it before saving another revision.")
        db.refresh(rule)
        write_revision(db, user, asset_for(db, user, rule.asset_id), rule, body)
        return committed(db, key, digest, describe(db, rule))

    @router.get("/drafts/{rule_id}/history")
    def history(rule_id: str, before_version: int | None = Query(default=None, ge=1),
                user: User = Depends(current_user), db: Session = Depends(get_db)):
        permitted(user)
        rule_for(db, user, rule_id)
        query = select(ConditionRuleRevision).where(ConditionRuleRevision.rule_id == rule_id)
        if before_version is not None:
            query = query.where(ConditionRuleRevision.version < before_version)
        rows = list(db.scalars(query.order_by(ConditionRuleRevision.version.desc()).limit(51)))
        return {"items": [revision_json(row) for row in rows[:50]],
                "next_before_version": rows[49].version if len(rows) > 50 else None}

    @router.post("/preview")
    def preview(body: RulePreview, user: User = Depends(current_user), db: Session = Depends(get_db)):
        allow(user, "engineer", "admin")
        asset = asset_for(db, user, body.asset_id)
        rows = list(db.scalars(select(Reading).where(Reading.asset_id == asset.id)
                               .order_by(Reading.timestamp.desc(), Reading.id.desc()).limit(501)))
        truncated = len(rows) > 500
        samples = [{"timestamp": r.timestamp, "quality": r.quality, body.channel: getattr(r, body.channel)}
                   for r in reversed(rows[:500])]
        result = evaluate(samples, body.channel, body.threshold, body.hysteresis,
                          body.persistence_seconds, body.maximum_gap_seconds)
        return {**result, "asset_tag": asset.tag, "rule": body.model_dump(), "sample_count": len(samples),
                "history_truncated": truncated,
                "first_observed_at": samples[0]["timestamp"] if samples else None,
                "last_observed_at": samples[-1]["timestamp"] if samples else None,
                "preview_only": True, "saved": False,
                "boundary": "Evaluates at most the latest 500 stored snapshots. Historical matches are not current alarms. No rule, episode, notification or equipment setting was changed."}

    return router
