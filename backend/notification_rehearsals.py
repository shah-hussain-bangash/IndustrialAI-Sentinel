"""Local simulations only. No transport, network client, email queue or worker."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update, func, or_, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .database import (NotificationRehearsal as Run, NotificationRehearsalEvent as Event, NotificationPlanRevision as Plan,
    NotificationPlanReview as Review, ConditionRule, ConditionRuleMatch, User, Audit, now)
from .security import allow, current_user, get_db
from .notification_plans import latest, plan_json, eligible_people

BOUNDARY="Local delivery rehearsal only. Queued means queued for manual simulation, never for email. Outcomes are simulated for the whole planned recipient group; no mailbox delivery is attempted or verified. No sender, network transport or background worker is connected."
OPEN=("queued","retry_wait")


class ConfirmedNote(BaseModel):
    model_config=ConfigDict(extra="forbid")
    reason:str=Field(min_length=5,max_length=1000)
    confirmed:Literal[True]
    @field_validator("confirmed",mode="before")
    @classmethod
    def confirm(cls,value):
        if value is not True:raise ValueError("Confirm the simulation-only action.")
        return value
    @field_validator("reason")
    @classmethod
    def note(cls,value):
        value=value.strip()
        if len(value)<5 or any(ord(c)<32 for c in value):raise ValueError("Provide a reason of at least five characters without control characters.")
        return value


class Enqueue(ConfirmedNote):
    expected_plan_version:int=Field(ge=1,strict=True)
    expected_rule_version:int=Field(ge=1,strict=True)
    expected_review_version:int=Field(ge=1,strict=True)
    match_id:str=Field(min_length=1,max_length=36)


class RunControl(ConfirmedNote):
    expected_version:int=Field(ge=1,strict=True)
    action:Literal["simulate_success","simulate_retryable_failure","simulate_permanent_failure","cancel"]


def run_json(row):
    return {"id":row.id,"rule_id":row.rule_id,"plan_version":row.plan_version,"review_version":row.review_version,"match_id":row.match_id,
        "recipients":row.recipients,"version":row.version,"state":row.state,"attempts":row.attempts,"next_attempt_at":row.next_attempt_at,
        "actor_name":row.actor_name,"reason":row.reason,"created":row.created,"simulation_only":True,"delivery_enabled":False}


def create_notification_rehearsal_router(asset_for,idempotent,finish):
    router=APIRouter(prefix="/api/notification-plans/rules",tags=["Local delivery rehearsals"])

    def rule_for(db,user,rule_id):
        allow(user,"engineer","admin");rule=db.get(ConditionRule,rule_id)
        if not rule:raise HTTPException(404,"Saved rule not found.")
        return rule,asset_for(db,user,rule.asset_id)

    def gate(db,rule,asset,run=None):
        plan=latest(db,rule.id)
        review=db.scalar(select(Review).where(Review.rule_id==rule.id).order_by(Review.version.desc()).limit(1))
        reasons=[]
        if not plan:reasons.append("Save a notification plan first.")
        elif plan.rule_version!=rule.version:reasons.append("The notification plan must use the current saved rule revision.")
        if not plan or not review or review.state!="approved" or review.plan_version!=plan.version or review.actor_id==plan.actor_id:
            reasons.append("Independent planning approval of this exact plan is required.")
        if run and (not plan or plan.version!=run.plan_version or not review or review.version!=run.review_version):
            reasons.append("The captured plan or review has changed since this rehearsal was queued.")
        if plan:
            for saved in plan.recipients:
                if not db.scalar(eligible_people(db,asset.site_id).where(User.id==saved["id"])):
                    reasons.append("A planned recipient no longer has eligible site access.");break
            if not 1<=len(plan.recipients)<=10:reasons.append("Select one to ten planned recipients.")
        return plan,review,reasons

    def run_for(db,rule,run_id):
        row=db.get(Run,run_id)
        if not row or row.rule_id!=rule.id:raise HTTPException(404,"Rehearsal not found.")
        return row

    def detail(db,user,rule,asset,row):
        _,_,reasons=gate(db,rule,asset,row);clock=now()
        events=list(db.scalars(select(Event).where(Event.rehearsal_id==row.id).order_by(Event.version)))
        match=db.get(ConditionRuleMatch,row.match_id)
        saved=db.get(Plan,(row.rule_id,row.plan_version))
        if not match or not saved or match.rule_id!=rule.id or match.rule_version!=saved.rule_version:
            raise HTTPException(409,"The captured rehearsal source is unavailable or inconsistent.")
        return {**run_json(row),"source_plan":plan_json(saved),
            "source_match":{"id":match.id,"rule_version":match.rule_version,"triggered_at":match.triggered_at,"state":match.state},
            "server_time":clock,"gate_reasons":reasons,
            "can_control":user.role=="admin" and row.state in OPEN,
            "attempt_due":row.state in OPEN and row.next_attempt_at<=clock,
            "history":[{"version":e.version,"action":e.action,"attempt_number":e.attempt_number,"check_reasons":e.check_reasons,"actor_name":e.actor_name,"reason":e.reason,"created":e.created} for e in events],
            "boundary":BOUNDARY}

    def event(db,user,asset,row,action,reason,check_reasons=None):
        db.add(Event(rehearsal_id=row.id,version=row.version,action=action,attempt_number=row.attempts,check_reasons=check_reasons or [],actor_id=user.id,actor_name=user.name,reason=reason,created=now()))
        db.add(Audit(site=asset.site,actor=user.name,action="Notification rehearsal "+action,target=asset.tag,
            details=f"Rehearsal {row.id}; version {row.version}; plan {row.plan_version}; review {row.review_version}. Reason: {reason}. Simulation only; no email queued or sent."))

    def complete(db,key,digest,user,rule,asset,row):
        try:
            db.flush();return finish(db,key,digest,detail(db,user,rule,asset,row))
        except IntegrityError:
            db.rollback();raise HTTPException(409,"The rehearsal changed or this approved plan/match already has a rehearsal. Reload before retrying.") from None

    @router.get("/{rule_id}/rehearsals")
    def listing(rule_id:str,before_id:str|None=Query(default=None,min_length=1,max_length=36),user:User=Depends(current_user),db:Session=Depends(get_db)):
        rule,asset=rule_for(db,user,rule_id);plan,review,reasons=gate(db,rule,asset)
        query=select(Run).where(Run.rule_id==rule.id)
        if before_id:
            cursor=run_for(db,rule,before_id)
            query=query.where(or_(Run.created<cursor.created,and_(Run.created==cursor.created,Run.id<cursor.id)))
        rows=list(db.scalars(query.order_by(Run.created.desc(),Run.id.desc()).limit(21)))
        matches=list(db.scalars(select(ConditionRuleMatch).where(ConditionRuleMatch.rule_id==rule.id,ConditionRuleMatch.rule_version==(plan.rule_version if plan else rule.version))
            .order_by(ConditionRuleMatch.triggered_at.desc(),ConditionRuleMatch.id).limit(21)))
        return {"plan":plan_json(plan) if plan else None,"latest_rule_version":rule.version,"review_version":review.version if review else 0,
            "server_time":now(),"can_enqueue":user.role=="admin" and not reasons,"gate_reasons":reasons,"items":[run_json(r) for r in rows[:20]],
            "next_before_id":rows[19].id if len(rows)>20 else None,
            "matches":[{"id":m.id,"triggered_at":m.triggered_at,"state":m.state} for m in matches[:20]],"matches_truncated":len(matches)>20,"boundary":BOUNDARY}

    @router.get("/{rule_id}/rehearsals/{run_id}")
    def get_run(rule_id:str,run_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
        rule,asset=rule_for(db,user,rule_id);return detail(db,user,rule,asset,run_for(db,rule,run_id))

    @router.post("/{rule_id}/rehearsals")
    def enqueue(rule_id:str,body:Enqueue,request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
        allow(user,"admin");rule,asset=rule_for(db,user,rule_id)
        key,digest,receipt=idempotent(db,request,user,body.model_dump())
        if receipt is not None:return receipt
        db.execute(update(ConditionRule).where(ConditionRule.id==rule.id).values(version=ConditionRule.version));db.refresh(rule)
        key,digest,receipt=idempotent(db,request,user,body.model_dump())
        if receipt is not None:return receipt
        plan=latest(db,rule.id)
        if plan:
            for person_id in sorted(p["id"] for p in plan.recipients):db.execute(update(User).where(User.id==person_id).values(role=User.role))
        plan,review,reasons=gate(db,rule,asset)
        if reasons:raise HTTPException(409," ".join(reasons))
        if (plan.version,rule.version,review.version)!=(body.expected_plan_version,body.expected_rule_version,body.expected_review_version):
            raise HTTPException(409,"The saved plan, rule or review changed. Reload before queueing a simulation.")
        match=db.get(ConditionRuleMatch,body.match_id)
        if not match or match.rule_id!=rule.id:raise HTTPException(404,"Saved match not found for this rule.")
        if match.rule_version!=plan.rule_version:raise HTTPException(409,"Choose a historical match from this plan's exact rule revision.")
        if db.scalar(select(func.count()).select_from(Run).where(Run.rule_id==rule.id))>=100:raise HTTPException(422,"This local build supports 100 saved rehearsals per rule.")
        row=Run(rule_id=rule.id,plan_version=plan.version,review_version=review.version,match_id=match.id,recipients=plan.recipients,
            version=1,state="queued",attempts=0,next_attempt_at=now(),actor_id=user.id,actor_name=user.name,reason=body.reason,created=now())
        try:
            db.add(row);db.flush();event(db,user,asset,row,"enqueue",body.reason)
            return complete(db,key,digest,user,rule,asset,row)
        except IntegrityError:
            db.rollback();raise HTTPException(409,"This exact approved plan and match already have a rehearsal. Open the existing record.") from None

    @router.post("/{rule_id}/rehearsals/{run_id}/control")
    def control(rule_id:str,run_id:str,body:RunControl,request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
        allow(user,"admin");rule,asset=rule_for(db,user,rule_id);row=run_for(db,rule,run_id)
        key,digest,receipt=idempotent(db,request,user,body.model_dump())
        if receipt is not None:return receipt
        db.execute(update(ConditionRule).where(ConditionRule.id==rule.id).values(version=ConditionRule.version));db.refresh(rule)
        db.execute(update(Run).where(Run.id==row.id).values(version=Run.version));db.refresh(row)
        key,digest,receipt=idempotent(db,request,user,body.model_dump())
        if receipt is not None:return receipt
        if row.version!=body.expected_version or row.state not in OPEN:raise HTTPException(409,"The rehearsal changed or is already terminal. Reload before continuing.")
        for person_id in sorted(p["id"] for p in row.recipients):db.execute(update(User).where(User.id==person_id).values(role=User.role))
        _,_,reasons=gate(db,rule,asset,row)
        action=body.action;note=body.reason
        if action=="cancel":row.state="cancelled"
        elif reasons:
            row.state="blocked";action="block"
        else:
            if now()<row.next_attempt_at:raise HTTPException(409,"The next simulated attempt is not due yet. Reload after its scheduled time.")
            row.attempts+=1
            if action=="simulate_success":row.state="simulated_success"
            elif action=="simulate_permanent_failure":row.state="simulated_failure"
            else:row.state="retry_wait" if row.attempts<3 else "exhausted"
        row.next_attempt_at=now()+30*(2**(row.attempts-1)) if row.state=="retry_wait" else None
        row.version+=1;event(db,user,asset,row,action,note,reasons if action=="block" else [])
        return complete(db,key,digest,user,rule,asset,row)

    return router
