"""Planning review only. Decisions never approve an email destination or enable delivery."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .database import NotificationPlanRevision as Plan, NotificationPlanReview as Review, ConditionRule, User, Audit
from .security import allow, current_user, get_db
from .notification_plans import latest, plan_json, eligible_people, address_configured

BOUNDARY = "Independent planning decision about this saved plan and its account identities only. It does not approve email addresses, prove recipient readiness, enable delivery, send or queue messages, grant access, or dispatch work. Current account/site checks are separate and may change."


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "rejected"]
    expected_plan_version: int = Field(ge=1, strict=True)
    expected_rule_version: int = Field(ge=1, strict=True)
    expected_review_version: int = Field(ge=0, strict=True)
    reason: str = Field(min_length=5, max_length=1000)
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def confirmation(cls,value):
        if value is not True:raise ValueError("Confirm the exact saved plan and the planning-only scope.")
        return value

    @field_validator("reason")
    @classmethod
    def note(cls,value):
        value=value.strip()
        if len(value)<5 or any(ord(c)<32 for c in value):raise ValueError("Provide a review note of at least five characters without control characters.")
        return value


def create_notification_review_router(asset_for,idempotent,finish):
    router=APIRouter(prefix="/api/notification-plans/rules",tags=["Independent notification planning review"])

    def rule_for(db,user,rule_id):
        allow(user,"engineer","admin")
        row=db.get(ConditionRule,rule_id)
        if not row:raise HTTPException(404,"Saved rule not found.")
        return row,asset_for(db,user,row.asset_id)

    def describe(db,row):
        plan=db.get(Plan,(row.rule_id,row.plan_version))
        return {"version":row.version,"plan_version":row.plan_version,"rule_version":plan.rule_version,"plan_name":plan.name,
            "state":row.state,"actor_name":row.actor_name,"reason":row.reason,"created":row.created}

    def status(db,user,rule,asset):
        plan=latest(db,rule.id)
        if not plan:raise HTTPException(409,"Save a notification plan before requesting its planning review.")
        event=db.scalar(select(Review).where(Review.rule_id==rule.id).order_by(Review.version.desc()).limit(1))
        checks=[]
        for saved in plan.recipients:
            person=db.scalar(eligible_people(db,asset.site_id).where(User.id==saved["id"]).execution_options(populate_existing=True))
            checks.append({"id":saved["id"],"name":saved["name"],"currently_eligible":person is not None,
                "email_address_configured":bool(person and address_configured(person.email))})
        independent=user.role=="admin" and user.id!=plan.actor_id
        return {"saved_plan":plan_json(plan),"latest_rule_version":rule.version,"plan_rule_is_current":plan.rule_version==rule.version,
            "review_version":event.version if event else 0,"current_decision":event.state if event and event.plan_version==plan.version else None,
            "last_review":describe(db,event) if event else None,"can_review":independent,
            "can_approve":independent and plan.rule_version==rule.version and bool(checks) and all(p["currently_eligible"] for p in checks),
            "recipient_checks":checks,"delivery_enabled":False,"boundary":BOUNDARY}

    @router.get("/{rule_id}/reviews")
    def get_reviews(rule_id:str,before_version:int|None=Query(default=None,ge=1),user:User=Depends(current_user),db:Session=Depends(get_db)):
        rule,asset=rule_for(db,user,rule_id);result=status(db,user,rule,asset)
        query=select(Review).where(Review.rule_id==rule.id)
        if before_version is not None:query=query.where(Review.version<before_version)
        rows=list(db.scalars(query.order_by(Review.version.desc()).limit(51)))
        return {**result,"items":[describe(db,row) for row in rows[:50]],"next_before_version":rows[49].version if len(rows)>50 else None}

    @router.post("/{rule_id}/reviews")
    def review(rule_id:str,body:ReviewInput,request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
        allow(user,"admin");rule,asset=rule_for(db,user,rule_id)
        key,digest,receipt=idempotent(db,request,user,body.model_dump())
        if receipt is not None:return receipt
        # Plan saves and decisions share the exact rule-head lock.
        db.execute(update(ConditionRule).where(ConditionRule.id==rule.id).values(version=ConditionRule.version));db.refresh(rule)
        key,digest,receipt=idempotent(db,request,user,body.model_dump())
        if receipt is not None:return receipt
        plan=latest(db,rule.id)
        if not plan:raise HTTPException(409,"Save a notification plan before reviewing it.")
        for person_id in sorted(p["id"] for p in plan.recipients):
            db.execute(update(User).where(User.id==person_id).values(role=User.role))
        result=status(db,user,rule,asset)
        if (plan.version,rule.version,result["review_version"])!=(body.expected_plan_version,body.expected_rule_version,body.expected_review_version):
            raise HTTPException(409,"The saved plan, rule or planning review changed. Reload before deciding.")
        if not result["can_review"]:raise HTTPException(403,"A different administrator from this plan revision’s author must review it.")
        if body.decision=="approved" and not result["can_approve"]:
            raise HTTPException(409,"Planning approval requires the current exact rule revision and eligible site reviewers. Reload or revise the plan first.")
        db.add(Review(rule_id=rule.id,version=result["review_version"]+1,plan_version=plan.version,state=body.decision,
            actor_id=user.id,actor_name=user.name,reason=body.reason))
        db.add(Audit(site=asset.site,actor=user.name,action="Notification plan planning review",target=asset.tag,
            details=f"Rule {rule.id}; plan revision {plan.version}; {body.decision}. Reason: {body.reason}. Planning only; no email destination authorization or delivery."))
        try:
            db.flush();return finish(db,key,digest,status(db,user,rule,asset))
        except IntegrityError:
            db.rollback();raise HTTPException(409,"Planning review changed concurrently. Reload before retrying.") from None

    return router
