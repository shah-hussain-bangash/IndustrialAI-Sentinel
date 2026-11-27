"""Preparation only. This module has no sender, queue, activation or worker."""
import re
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .database import NotificationPlanRevision as Plan, ConditionRule, ConditionRuleRevision, ConditionRuleMatch, User, SiteMembership, Audit
from .security import allow, current_user, get_db
from .rule_reviews import match_evidence, current_review, review_json

BOUNDARY = "Inactive notification plan only. No email is sent or queued; no sender, retry worker, escalation or automatic delivery is connected. Saving a recipient does not grant access. Historical previews are not live notification events."


class PlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0, strict=True)
    expected_rule_version: int = Field(ge=1, strict=True)
    name: str = Field(min_length=1, max_length=120)
    recipient_ids: list[str] = Field(min_length=1, max_length=10)
    reason: str = Field(min_length=5, max_length=1000)

    @field_validator("name", "reason")
    @classmethod
    def text(cls, value, info):
        value=value.strip()
        if len(value)<(5 if info.field_name=="reason" else 1) or any(ord(c)<32 for c in value):
            raise ValueError("Provide a name and a reason of at least five characters without control characters.")
        return value

    @field_validator("recipient_ids")
    @classmethod
    def people(cls,value):
        if len(set(value))!=len(value) or any(not 1<=len(v)<=36 or v.strip()!=v for v in value):
            raise ValueError("Select one to ten distinct eligible account identities.")
        return value


class PreviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_plan_version: int = Field(ge=1, strict=True)
    match_id: str = Field(min_length=1, max_length=36)


def latest(db, rule_id):
    return db.scalar(select(Plan).where(Plan.rule_id==rule_id).order_by(Plan.version.desc()).limit(1))


def plan_json(row):
    return {"version":row.version,"rule_version":row.rule_version,"name":row.name,"recipients":row.recipients,
        "actor_name":row.actor_name,"reason":row.reason,"created":row.created,"active":False,"channel":"email","event":"new_saved_rule_match"}


def eligible_people(db,site_id):
    return select(User).join(SiteMembership,SiteMembership.user_id==User.id).where(SiteMembership.site_id==site_id,User.role.in_(["engineer","admin"]))


def address_configured(email):
    # A planning indicator, never a deliverability or mailbox-ownership guarantee.
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",email) and not email.lower().endswith((".local",".invalid",".example",".test")))


def create_notification_plan_router(asset_for,idempotent,finish):
    router=APIRouter(prefix="/api/notification-plans/rules",tags=["Inactive notification planning"])

    def rule_for(db,user,rule_id):
        allow(user,"engineer","admin")
        rule=db.get(ConditionRule,rule_id)
        if not rule:raise HTTPException(404,"Saved rule not found.")
        return rule,asset_for(db,user,rule.asset_id)

    @router.get("/{rule_id}")
    def get_plan(rule_id:str,recipient_name:str=Query(default="",max_length=100),user:User=Depends(current_user),db:Session=Depends(get_db)):
        rule,asset=rule_for(db,user,rule_id);plan=latest(db,rule.id)
        people=eligible_people(db,asset.site_id)
        if recipient_name.strip():people=people.where(User.name.icontains(recipient_name.strip(),autoescape=True))
        recipients=list(db.scalars(people.order_by(User.name,User.id).limit(101)))
        version=plan.rule_version if plan else rule.version
        matches=list(db.scalars(select(ConditionRuleMatch).where(ConditionRuleMatch.rule_id==rule.id,ConditionRuleMatch.rule_version==version)
            .order_by(ConditionRuleMatch.triggered_at.desc(),ConditionRuleMatch.id).limit(21)))
        revision=db.get(ConditionRuleRevision,(rule.id,rule.version))
        return {"rule_id":rule.id,"latest_rule_version":rule.version,"rule_name":revision.name,"asset_tag":asset.tag,
            "current":plan_json(plan) if plan else None,"recipients":[{"id":p.id,"name":p.name,"role":p.role} for p in recipients[:100]],
            "recipients_truncated":len(recipients)>100,"recent_matches":[{"id":m.id,"rule_version":m.rule_version,"state":m.state,"triggered_at":m.triggered_at} for m in matches[:20]],
            "matches_truncated":len(matches)>20,"delivery_enabled":False,"boundary":BOUNDARY}

    @router.post("/{rule_id}")
    def save(rule_id:str,body:PlanInput,request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
        rule,asset=rule_for(db,user,rule_id)
        key,digest,receipt=idempotent(db,request,user,body.model_dump())
        if receipt is not None:return receipt
        db.execute(update(ConditionRule).where(ConditionRule.id==rule.id).values(version=ConditionRule.version));db.refresh(rule)
        key,digest,receipt=idempotent(db,request,user,body.model_dump())
        if receipt is not None:return receipt
        old=latest(db,rule.id)
        if rule.version!=body.expected_rule_version or (old.version if old else 0)!=body.expected_version:
            raise HTTPException(409,"The saved rule or notification plan changed. Reload before saving.")
        # Serialize eligibility checks with current account-role/site changes.
        for person_id in sorted(body.recipient_ids):
            db.execute(update(User).where(User.id==person_id).values(role=User.role))
        people=list(db.scalars(eligible_people(db,asset.site_id).where(User.id.in_(body.recipient_ids)).execution_options(populate_existing=True)))
        if len(people)!=len(body.recipient_ids):raise HTTPException(422,"Select engineers or administrators with current access to this equipment site.")
        by_id={person.id:person for person in people}
        row=Plan(rule_id=rule.id,version=body.expected_version+1,rule_version=rule.version,name=body.name,
            recipients=[{"id":pid,"name":by_id[pid].name} for pid in body.recipient_ids],actor_id=user.id,actor_name=user.name,reason=body.reason)
        db.add(row);db.add(Audit(site=asset.site,actor=user.name,action="Notification plan draft saved",target=asset.tag,
            details=f"Rule {rule.id}; rule revision {rule.version}; plan revision {row.version}; {len(people)} planned recipients. Reason: {body.reason}. Inactive; no email queued or sent."))
        try:
            db.flush();return finish(db,key,digest,plan_json(row))
        except IntegrityError:
            db.rollback();raise HTTPException(409,"Notification plan changed concurrently. Reload before retrying.") from None

    @router.get("/{rule_id}/history")
    def history(rule_id:str,before_version:int|None=Query(default=None,ge=1),user:User=Depends(current_user),db:Session=Depends(get_db)):
        rule_for(db,user,rule_id)
        query=select(Plan).where(Plan.rule_id==rule_id)
        if before_version is not None:query=query.where(Plan.version<before_version)
        rows=list(db.scalars(query.order_by(Plan.version.desc()).limit(51)))
        return {"items":[plan_json(row) for row in rows[:50]],"next_before_version":rows[49].version if len(rows)>50 else None,"boundary":BOUNDARY}

    @router.post("/{rule_id}/preview")
    def preview(rule_id:str,body:PreviewInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
        rule,asset=rule_for(db,user,rule_id);plan=latest(db,rule.id)
        if not plan or plan.version!=body.expected_plan_version:raise HTTPException(409,"The saved notification plan changed or is missing. Reload before previewing.")
        match=db.get(ConditionRuleMatch,body.match_id)
        if not match or match.rule_id!=rule.id:raise HTTPException(404,"Saved match not found for this rule.")
        if match.rule_version!=plan.rule_version:raise HTTPException(409,"Choose a match captured under this plan’s exact rule revision.")
        recipients=[]
        for saved in plan.recipients:
            person=db.scalar(eligible_people(db,asset.site_id).where(User.id==saved["id"]))
            recipients.append({"id":saved["id"],"name":saved["name"],"currently_eligible":person is not None,
                "email_address_configured":bool(person and address_configured(person.email))})
        evidence=match_evidence(db,match,asset)
        return {"preview_only":True,"delivery_enabled":False,"queued":False,"plan":plan_json(plan),"plan_rule_is_current":plan.rule_version==rule.version,
            "recipients":recipients,"eligible_configured_count":sum(r["currently_eligible"] and r["email_address_configured"] for r in recipients),
            "subject":f"[Sentinel draft] {asset.tag}: {evidence['rule']['name']}","match_id":match.id,"match_route":"#conditions/"+match.id,
            "evidence":evidence,"review":review_json(current_review(db,match.id)),"boundary":BOUNDARY}

    return router
