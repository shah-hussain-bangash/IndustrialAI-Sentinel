"""Explicit administrator activation of an independently approved future window."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .database import MaintenanceWindowDraft as Draft, MaintenanceWindowRevision as Revision, MaintenanceWindowReview as Review, MaintenanceWindowControl as Control, MaintenanceWindowSuppression as Suppression, Asset, User, Audit, now
from .security import current_user, get_db, allow
from .maintenance_policy import SCOPE, intervals, state
from .maintenance_windows import revision_json


class WindowControl(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["activate", "cancel"]
    expected_draft_version: int = Field(ge=1, strict=True)
    expected_review_version: int = Field(ge=1, strict=True)
    expected_control_version: int = Field(ge=0, strict=True)
    reason: str = Field(min_length=5, max_length=1000)
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def confirmation(cls, value):
        if value is not True: raise ValueError("Confirm the exact window and its suppression scope.")
        return value

    @field_validator("reason")
    @classmethod
    def note(cls, value):
        value=value.strip()
        if len(value)<5 or any(ord(c)<32 for c in value): raise ValueError("Provide a reason of at least five characters without control characters.")
        return value


def create_maintenance_control_router(asset_for, idempotent, finish):
    router=APIRouter(prefix="/api/maintenance-windows", tags=["Controlled maintenance windows"])

    def draft_for(db,user,draft_id):
        allow(user,"engineer","admin")
        row=db.get(Draft,draft_id)
        if not row: raise HTTPException(404,"Window plan not found.")
        return row,asset_for(db,user,row.asset_id)

    def status(db,user,row):
        clock=now(); revision=db.get(Revision,(row.id,row.version))
        if not revision: raise HTTPException(409,"Window revision is unavailable.")
        reviews=db.scalar(select(Review).where(Review.draft_id==row.id).order_by(Review.version.desc()).limit(1))
        history=list(db.scalars(select(Control).where(Control.draft_id==row.id).order_by(Control.version)))
        current=state(db,row.id,clock)
        count=db.scalar(select(func.count()).select_from(Suppression).where(Suppression.draft_id==row.id))
        recent=list(db.scalars(select(Suppression).where(Suppression.draft_id==row.id).order_by(Suppression.created.desc(),Suppression.rule_id,Suppression.reading_id).limit(50)))
        return {"draft_version":row.version,"review_version":reviews.version if reviews else 0,"control_version":history[-1].version if history else 0,
            "state":current,"server_time":clock,"saved_revision":revision_json(revision),
            "can_activate":user.role=="admin" and not history and revision.starts_at>clock and bool(reviews and reviews.state=="approved" and reviews.draft_version==row.version),
            "can_cancel":user.role=="admin" and current in ("scheduled","suppressing"),
            "history":[{"version":r.version,"action":r.action,"draft_version":r.draft_version,"review_version":r.review_version,"actor_name":r.actor_name,"reason":r.reason,"created":r.created} for r in history],
            "suppressed_count":count,"recent_suppressions":[{"rule_id":r.rule_id,"rule_version":r.rule_version,"reading_id":r.reading_id,"observed_at":r.observed_at,"created":r.created} for r in recent],
            "suppression_history_truncated":count>50,"scope":SCOPE}

    @router.get("/status")
    def equipment_status(asset_id:str=Query(min_length=1,max_length=36),user:User=Depends(current_user),db:Session=Depends(get_db)):
        asset_for(db,user,asset_id);clock=now()
        rows=list(db.scalars(select(Draft).where(Draft.asset_id==asset_id)))
        return {"server_time":clock,"items":[{"id":r.id,"state":s,"name":db.get(Revision,(r.id,r.version)).name} for r in rows if (s:=state(db,r.id,clock)) in ("scheduled","suppressing")],"scope":SCOPE}

    @router.get("/drafts/{draft_id}/control")
    def get_control(draft_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
        row,_=draft_for(db,user,draft_id)
        return status(db,user,row)

    @router.post("/drafts/{draft_id}/control")
    def control(draft_id:str,body:WindowControl,request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
        allow(user,"admin");row,asset=draft_for(db,user,draft_id)
        key,digest,receipt=idempotent(db,request,user,body.model_dump())
        if receipt is not None:return receipt
        # Same asset lock as snapshot processing, then the draft lock used by edits/reviews.
        db.execute(update(Asset).where(Asset.id==asset.id).values(version=Asset.version))
        db.execute(update(Draft).where(Draft.id==row.id).values(version=Draft.version));db.refresh(row)
        key,digest,receipt=idempotent(db,request,user,body.model_dump())
        if receipt is not None:return receipt
        current=status(db,user,row)
        if (row.version,current["review_version"],current["control_version"])!=(body.expected_draft_version,body.expected_review_version,body.expected_control_version):
            raise HTTPException(409,"The saved plan, review or control state changed. Reload before continuing.")
        if body.action=="activate":
            if not current["can_activate"]:raise HTTPException(409,"Activation requires independent approval of this exact revision, a future start, and a plan that has never been activated.")
            revision=db.get(Revision,(row.id,row.version))
            if any(start<revision.ends_at and end>revision.starts_at and start<end for _,start,end in intervals(db,asset.id)):
                raise HTTPException(409,"An activated window overlaps this interval for the same equipment. Cancel or choose a separate non-overlapping plan.")
        elif not current["can_cancel"]:
            raise HTTPException(409,"Only a scheduled or currently suppressing window can be cancelled.")
        db.add(Control(draft_id=row.id,version=current["control_version"]+1,draft_version=row.version,review_version=current["review_version"],action=body.action,actor_id=user.id,actor_name=user.name,reason=body.reason))
        db.add(Audit(site=asset.site,actor=user.name,action="Maintenance window "+("activated" if body.action=="activate" else "cancelled"),target=asset.tag,
            details=f"Plan {row.id}; revision {row.version}; review {current['review_version']}. Reason: {body.reason}. New saved-rule triggers only; no physical work dispatched."))
        try:
            db.flush();return finish(db,key,digest,status(db,user,row))
        except IntegrityError:
            db.rollback();raise HTTPException(409,"Window control changed concurrently. Reload before retrying.") from None

    return router
