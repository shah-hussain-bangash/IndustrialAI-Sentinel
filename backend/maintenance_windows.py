"""Preparation only: saved maintenance-window drafts never affect rule evaluation."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .database import MaintenanceWindowDraft, MaintenanceWindowRevision, MaintenanceWindowReview, Asset, User, Audit
from typing import Literal
from .security import allow, current_user, get_db

BOUNDARY = "Inactive planning draft only. Saving does not suppress signals, pause rules, resolve reviews or dispatch maintenance. Activation and operational suppression are not implemented in this step."


class WindowCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str = Field(min_length=1, max_length=36)
    name: str = Field(min_length=1, max_length=120)
    starts_at: int = Field(ge=0, le=4102444800, strict=True)
    ends_at: int = Field(ge=0, le=4102444800, strict=True)
    reason: str = Field(min_length=5, max_length=1000)

    @field_validator("name", "reason")
    @classmethod
    def text(cls, value, info):
        value = value.strip()
        if len(value) < (5 if info.field_name == "reason" else 1) or any(ord(c) < 32 for c in value):
            raise ValueError("Provide a name and a reason of at least five characters, without control characters.")
        return value

    @model_validator(mode="after")
    def range(self):
        if not 0 < self.ends_at - self.starts_at <= 604800:
            raise ValueError("The end must follow the start by no more than seven days.")
        return self


class WindowUpdate(WindowCreate):
    expected_version: int = Field(ge=1)


class PlanningReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "rejected"]
    expected_draft_version: int = Field(ge=1, strict=True)
    expected_review_version: int = Field(ge=0, strict=True)
    reason: str = Field(min_length=5, max_length=1000)
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def confirmation(cls, value):
        if value is not True: raise ValueError("Confirm the exact saved revision before reviewing.")
        return value

    @field_validator("reason")
    @classmethod
    def note(cls, value):
        value = value.strip()
        if len(value) < 5 or any(ord(c) < 32 for c in value):
            raise ValueError("Provide a review note of at least five characters, without control characters.")
        return value


def review_json(row):
    return {"version": row.version, "draft_version": row.draft_version, "state": row.state,
            "actor_name": row.actor_name, "reason": row.reason, "created": row.created}


def revision_json(row):
    return {"version": row.version, "name": row.name, "starts_at": row.starts_at, "ends_at": row.ends_at,
            "reason": row.reason, "actor_name": row.actor_name, "created": row.created}


def create_maintenance_window_router(asset_for, idempotent, finish):
    router = APIRouter(prefix="/api/maintenance-windows", tags=["Inactive maintenance-window planning"])

    def draft_for(db, user, draft_id):
        allow(user, "engineer", "admin")
        row = db.get(MaintenanceWindowDraft, draft_id)
        if row is None: raise HTTPException(404, "Window draft not found.")
        return row, asset_for(db, user, row.asset_id)

    def describe(db, row):
        revision = db.get(MaintenanceWindowRevision, (row.id, row.version))
        if revision is None: raise HTTPException(409, "Draft history is inconsistent. Ask an administrator to check it.")
        return {"id": row.id, "asset_id": row.asset_id, "state": "draft", "active": False, **revision_json(revision)}

    def save_revision(db, user, asset, row, body):
        db.add(MaintenanceWindowRevision(draft_id=row.id, version=row.version, name=body.name, starts_at=body.starts_at,
            ends_at=body.ends_at, reason=body.reason, actor_id=user.id, actor_name=user.name))
        db.add(Audit(site=asset.site, actor=user.name, action="Maintenance window draft saved", target=asset.tag,
            details=f"Draft {row.id}; revision {row.version}; {body.name}. Reason: {body.reason}. Inactive plan; no operational suppression."))
        db.flush()

    def complete(db, key, digest, row):
        try:
            return finish(db, key, digest, describe(db, row))
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Draft changed concurrently. Reload before retrying.") from None

    @router.get("/drafts")
    def listing(asset_id: str = Query(min_length=1, max_length=36), user: User = Depends(current_user), db: Session = Depends(get_db)):
        allow(user, "engineer", "admin"); asset_for(db, user, asset_id)
        rows = list(db.scalars(select(MaintenanceWindowDraft).where(MaintenanceWindowDraft.asset_id == asset_id)
            .order_by(MaintenanceWindowDraft.created.desc(), MaintenanceWindowDraft.id).limit(101)))
        return {"items": [describe(db, row) for row in rows[:100]], "truncated": len(rows) > 100, "boundary": BOUNDARY}

    @router.post("/drafts", status_code=201)
    def create(body: WindowCreate, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
        allow(user, "engineer", "admin"); asset = asset_for(db, user, body.asset_id)
        key, digest, receipt = idempotent(db, request, user, body.model_dump())
        if receipt is not None: return receipt
        db.execute(update(Asset).where(Asset.id == asset.id).values(version=Asset.version))
        key, digest, receipt = idempotent(db, request, user, body.model_dump())
        if receipt is not None: return receipt
        count = db.scalar(select(func.count()).select_from(MaintenanceWindowDraft).where(MaintenanceWindowDraft.asset_id == asset.id))
        if count >= 100: raise HTTPException(422, "This equipment has 100 window drafts. Revise an existing draft instead.")
        row = MaintenanceWindowDraft(asset_id=asset.id, version=1)
        db.add(row); db.flush(); save_revision(db, user, asset, row, body)
        return complete(db, key, digest, row)

    @router.post("/drafts/{draft_id}")
    def revise(draft_id: str, body: WindowUpdate, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
        row, asset = draft_for(db, user, draft_id)
        if body.asset_id != row.asset_id: raise HTTPException(422, "A window draft cannot move to different equipment.")
        key, digest, receipt = idempotent(db, request, user, body.model_dump())
        if receipt is not None: return receipt
        db.execute(update(MaintenanceWindowDraft).where(MaintenanceWindowDraft.id == row.id).values(version=MaintenanceWindowDraft.version))
        db.refresh(row)
        key, digest, receipt = idempotent(db, request, user, body.model_dump())
        if receipt is not None: return receipt
        if row.version != body.expected_version: raise HTTPException(409, "This window draft changed. Reload it before saving.")
        row.version += 1; save_revision(db, user, asset, row, body)
        return complete(db, key, digest, row)

    @router.get("/drafts/{draft_id}/history")
    def history(draft_id: str, before_version: int | None = Query(default=None, ge=1), user: User = Depends(current_user), db: Session = Depends(get_db)):
        row, asset = draft_for(db, user, draft_id)
        query = select(MaintenanceWindowRevision).where(MaintenanceWindowRevision.draft_id == row.id)
        if before_version is not None: query = query.where(MaintenanceWindowRevision.version < before_version)
        rows = list(db.scalars(query.order_by(MaintenanceWindowRevision.version.desc()).limit(51)))
        return {"items": [revision_json(item) for item in rows[:50]], "next_before_version": rows[49].version if len(rows) > 50 else None, "boundary": BOUNDARY}

    def review_status(db, user, row):
        saved = db.get(MaintenanceWindowRevision, (row.id, row.version))
        if saved is None: raise HTTPException(409, "Saved revision is missing. Ask an administrator to check it.")
        latest = db.scalar(select(MaintenanceWindowReview).where(MaintenanceWindowReview.draft_id == row.id)
            .order_by(MaintenanceWindowReview.version.desc()).limit(1))
        return {"draft_version": row.version, "review_version": latest.version if latest else 0,
            "current_decision": latest.state if latest and latest.draft_version == row.version else None,
            "last_review": review_json(latest) if latest else None, "saved_revision": revision_json(saved),
            "can_review": user.role == "admin" and saved.actor_id != user.id, "boundary": BOUNDARY}

    @router.get("/drafts/{draft_id}/reviews")
    def reviews(draft_id: str, before_version: int | None = Query(default=None, ge=1), user: User = Depends(current_user), db: Session = Depends(get_db)):
        row, _ = draft_for(db, user, draft_id)
        query = select(MaintenanceWindowReview).where(MaintenanceWindowReview.draft_id == row.id)
        if before_version is not None: query = query.where(MaintenanceWindowReview.version < before_version)
        rows = list(db.scalars(query.order_by(MaintenanceWindowReview.version.desc()).limit(51)))
        return {**review_status(db, user, row), "items": [review_json(item) for item in rows[:50]],
            "next_before_version": rows[49].version if len(rows) > 50 else None}

    @router.post("/drafts/{draft_id}/reviews")
    def review(draft_id: str, body: PlanningReview, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
        allow(user, "admin")
        row, asset = draft_for(db, user, draft_id)
        key, digest, receipt = idempotent(db, request, user, body.model_dump())
        if receipt is not None: return receipt
        # All draft revisions and planning decisions serialize on the same head row.
        db.execute(update(MaintenanceWindowDraft).where(MaintenanceWindowDraft.id == row.id).values(version=MaintenanceWindowDraft.version))
        db.refresh(row)
        key, digest, receipt = idempotent(db, request, user, body.model_dump())
        if receipt is not None: return receipt
        status = review_status(db, user, row)
        if row.version != body.expected_draft_version or status["review_version"] != body.expected_review_version:
            raise HTTPException(409, "The saved window or its review changed. Reload both before reviewing.")
        if not status["can_review"]:
            raise HTTPException(403, "A different administrator must review the author’s saved revision.")
        db.add(MaintenanceWindowReview(draft_id=row.id, version=status["review_version"] + 1, draft_version=row.version,
            state=body.decision, actor_id=user.id, actor_name=user.name, reason=body.reason))
        db.add(Audit(site=asset.site, actor=user.name, action="Maintenance window planning review", target=asset.tag,
            details=f"Draft {row.id}; revision {row.version}; {body.decision}. Reason: {body.reason}. Planning only; no operational suppression."))
        try:
            db.flush()
            return finish(db, key, digest, review_status(db, user, row))
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Planning review changed concurrently. Reload before retrying.") from None

    return router
