"""Review records are separate from signal state and maintenance completion."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from .database import ConditionRuleReview, ConditionRuleMatch, ConditionRule, Audit, User
from .security import allow, current_user, get_db


def review_json(row):
    return {"state": row.state if row else "unreviewed", "version": row.version if row else 0,
            "actor_name": row.actor_name if row else None, "reason": row.reason if row else None,
            "created": row.created if row else None}


def current_review(db, match_id):
    return db.scalar(select(ConditionRuleReview).where(ConditionRuleReview.match_id == match_id)
                     .order_by(ConditionRuleReview.version.desc()).limit(1))


class ReviewCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["acknowledge", "resolve"]
    expected_version: int = Field(ge=0)
    reason: str = Field(min_length=5, max_length=1000)

    @field_validator("reason")
    @classmethod
    def reason_text(cls, value):
        value = value.strip()
        if len(value) < 5 or any(ord(c) < 32 for c in value):
            raise ValueError("Provide a review note of at least five characters without control characters.")
        return value


def create_rule_review_router(asset_for, idempotent, finish):
    router = APIRouter(prefix="/api/condition-rules/matches", tags=["Rule match review"])

    def match_for(db, user, match_id):
        allow(user, "engineer", "admin")
        match = db.get(ConditionRuleMatch, match_id)
        if match is None: raise HTTPException(404, "Rule match not found.")
        rule = db.get(ConditionRule, match.rule_id)
        return match, asset_for(db, user, rule.asset_id)

    @router.get("/{match_id}/reviews")
    def history(match_id: str, before_version: int | None = Query(default=None, ge=1),
                user: User = Depends(current_user), db: Session = Depends(get_db)):
        match, asset = match_for(db, user, match_id)
        query = select(ConditionRuleReview).where(ConditionRuleReview.match_id == match_id)
        if before_version is not None: query = query.where(ConditionRuleReview.version < before_version)
        rows = list(db.scalars(query.order_by(ConditionRuleReview.version.desc()).limit(51)))
        return {"current": review_json(current_review(db, match_id)), "signal_state": match.state,
                "items": [review_json(row) for row in rows[:50]],
                "next_before_version": rows[49].version if len(rows) > 50 else None}

    @router.post("/{match_id}/review")
    def transition(match_id: str, body: ReviewCommand, request: Request,
                   user: User = Depends(current_user), db: Session = Depends(get_db)):
        match, asset = match_for(db, user, match_id)
        key, digest, receipt = idempotent(db, request, user, body.model_dump())
        if receipt is not None: return receipt
        # A row lock serializes reviews with each other and with evaluator closure.
        db.execute(update(ConditionRuleMatch).where(ConditionRuleMatch.id == match_id).values(state=ConditionRuleMatch.state))
        db.refresh(match)
        previous = current_review(db, match_id)
        state, version = (previous.state, previous.version) if previous else ("unreviewed", 0)
        if version != body.expected_version:
            raise HTTPException(409, "This review changed. Reload the match before submitting again.")
        if body.action == "acknowledge" and state != "unreviewed":
            raise HTTPException(409, "Only an unreviewed match can be acknowledged.")
        if body.action == "resolve" and (state != "acknowledged" or match.state == "active"):
            raise HTTPException(409, "Acknowledge the match first. An active signal must end before its review can be resolved.")
        row = ConditionRuleReview(match_id=match_id, version=version + 1,
                                  state="acknowledged" if body.action == "acknowledge" else "resolved",
                                  actor_id=user.id, actor_name=user.name, reason=body.reason)
        db.add(row)
        db.add(Audit(site=asset.site, actor=user.name, action="Rule match " + row.state, target=asset.tag,
                     details=f"Match {match_id}; rule {match.rule_id}; revision {match.rule_version}; review {row.version}. Note: {body.reason}. Review only; no physical maintenance completion."))
        db.flush()
        return finish(db, key, digest, {"match_id": match_id, "review": review_json(row), "signal_state": match.state})

    return router
