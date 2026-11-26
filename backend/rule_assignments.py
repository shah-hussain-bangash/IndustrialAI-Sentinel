"""Local review responsibility; assignments never grant equipment access."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from .database import ConditionRuleAssignment, ConditionRuleMatch, ConditionRule, User, SiteMembership, Audit
from .security import allow, current_user, get_db


def current_assignment(db, match_id):
    return db.scalar(select(ConditionRuleAssignment).where(ConditionRuleAssignment.match_id == match_id)
                     .order_by(ConditionRuleAssignment.version.desc()).limit(1))


def eligible(db, owner_id, site_id):
    return db.scalar(select(User.id).join(SiteMembership, SiteMembership.user_id == User.id)
                     .where(User.id == owner_id, User.role.in_(['engineer', 'admin']), SiteMembership.site_id == site_id)) is not None


def assignment_json(row):
    return {"version": row.version if row else 0, "owner_id": row.owner_id if row else None,
            "owner_name": row.owner_name if row else None, "actor_name": row.actor_name if row else None,
            "reason": row.reason if row else None, "created": row.created if row else None}


def ownership_for(db, match_id, site_id):
    row = current_assignment(db, match_id)
    return {**assignment_json(row), 'eligible': bool(row and row.owner_id and eligible(db, row.owner_id, site_id))}


class AssignmentCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    owner_id: str | None = Field(min_length=1, max_length=36)
    expected_version: int = Field(ge=0)
    reason: str = Field(min_length=5, max_length=1000)

    @field_validator('reason')
    @classmethod
    def clean_reason(cls, value):
        value = value.strip()
        if len(value) < 5 or any(ord(c) < 32 for c in value):
            raise ValueError('Provide an assignment note of at least five characters without control characters.')
        return value


def create_rule_assignment_router(asset_for, idempotent, finish):
    from .rule_reviews import current_review
    router = APIRouter(prefix='/api/condition-rules/matches', tags=['Match ownership'])

    def match_for(db, user, match_id):
        allow(user, 'engineer', 'admin')
        match = db.get(ConditionRuleMatch, match_id)
        if match is None: raise HTTPException(404, 'Rule match not found.')
        rule = db.get(ConditionRule, match.rule_id)
        return match, asset_for(db, user, rule.asset_id)

    @router.get('/{match_id}/ownership')
    def ownership(match_id: str, before_version: int | None = Query(default=None, ge=1),
                  reviewer_name: str = Query(default='', max_length=100),
                  user: User = Depends(current_user), db: Session = Depends(get_db)):
        match, asset = match_for(db, user, match_id)
        row = current_assignment(db, match_id)
        reviewers = select(User).join(SiteMembership, SiteMembership.user_id == User.id).where(
            User.role.in_(['engineer', 'admin']), SiteMembership.site_id == asset.site_id)
        if reviewer_name.strip(): reviewers = reviewers.where(User.name.icontains(reviewer_name.strip(), autoescape=True))
        candidates = list(db.scalars(reviewers.order_by(User.name, User.id).limit(101)))
        history = select(ConditionRuleAssignment).where(ConditionRuleAssignment.match_id == match_id)
        if before_version is not None: history = history.where(ConditionRuleAssignment.version < before_version)
        rows = list(db.scalars(history.order_by(ConditionRuleAssignment.version.desc()).limit(51)))
        review = current_review(db, match_id)
        return {'current': assignment_json(row), 'owner_eligible': bool(row and row.owner_id and eligible(db, row.owner_id, asset.site_id)),
                'review_state': review.state if review else 'unreviewed',
                'reviewers': [{'id': person.id, 'name': person.name, 'role': person.role} for person in candidates[:100]],
                'reviewers_truncated': len(candidates) > 100,
                'items': [assignment_json(item) for item in rows[:50]],
                'next_before_version': rows[49].version if len(rows) > 50 else None}

    @router.post('/{match_id}/ownership')
    def assign(match_id: str, body: AssignmentCommand, request: Request,
               user: User = Depends(current_user), db: Session = Depends(get_db)):
        match, asset = match_for(db, user, match_id)
        key, digest, receipt = idempotent(db, request, user, body.model_dump())
        if receipt is not None: return receipt
        # The same match lock serializes assignment, review resolution and evaluator changes.
        db.execute(update(ConditionRuleMatch).where(ConditionRuleMatch.id == match_id).values(state=ConditionRuleMatch.state))
        previous = current_assignment(db, match_id)
        if (previous.version if previous else 0) != body.expected_version:
            raise HTTPException(409, 'Ownership changed. Reload before submitting again.')
        review = current_review(db, match_id)
        if review and review.state == 'resolved': raise HTTPException(409, 'A resolved review retains its assignment history. Ownership cannot be changed.')
        if (previous.owner_id if previous else None) == body.owner_id:
            raise HTTPException(409, 'Choose a different reviewer or clear the current assignment.')
        owner = None
        if body.owner_id is not None:
            # Serializes with account-role/site updates before eligibility is checked.
            db.execute(update(User).where(User.id == body.owner_id).values(role=User.role))
            if not eligible(db, body.owner_id, asset.site_id):
                raise HTTPException(422, 'Choose an engineer or administrator with current access to this equipment site.')
            owner = db.get(User, body.owner_id)
            db.refresh(owner)
        row = ConditionRuleAssignment(match_id=match_id, version=body.expected_version + 1,
                                      owner_id=owner.id if owner else None, owner_name=owner.name if owner else None,
                                      actor_id=user.id, actor_name=user.name, reason=body.reason)
        db.add(row)
        db.add(Audit(site=asset.site, actor=user.name, action='Condition review ownership changed', target=asset.tag,
                     details=f'Match {match_id}; assignment {row.version}; owner {row.owner_name or "Unassigned"}. Note: {body.reason}. Responsibility only; no access grant, notification or maintenance dispatch.'))
        db.flush()
        return finish(db, key, digest, {'match_id': match_id, 'current': assignment_json(row)})

    return router
