"""Review records are separate from signal state and maintenance completion."""
import math
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update, func, and_, or_, case
from sqlalchemy.orm import Session
from .database import ConditionRuleReview, ConditionRuleMatch, ConditionRule, ConditionRuleRevision, ConditionRuleAssignment, ConditionMatchInvestigation, Investigation, Asset, Audit, User, Reading, now
from .rule_assignments import ownership_for
from .inbox_investigations import investigation_summary
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


def match_evidence(db, match, asset):
    revision = db.get(ConditionRuleRevision, (match.rule_id, match.rule_version))
    reading = db.get(Reading, match.trigger_reading_id)
    # A malformed cross-equipment reference must never disclose another site's snapshot.
    if revision is None or reading is None or reading.asset_id != asset.id:
        raise HTTPException(409, "The linked evidence is unavailable or inconsistent. Ask an administrator to check the record.")
    units = {"vibration": "mm/s", "temperature": "°C", "pressure": "bar", "flow": "m³/h"}
    values = {channel: getattr(reading, channel) for channel in units}
    return {"match_id": match.id, "asset": {"tag": asset.tag, "name": asset.name, "site": asset.site},
            "rule": {"id": match.rule_id, "version": revision.version, "name": revision.name,
                     "settings": revision.settings, "actor_name": revision.actor_name,
                     "created": revision.created, "reason": revision.reason},
            "match": {"signal_state": match.state, "started_at": match.started_at,
                      "triggered_at": match.triggered_at, "ended_at": match.ended_at},
            "snapshot": {"id": reading.id, "timestamp": reading.timestamp, "quality": reading.quality,
                         "signals": [{"channel": channel, "unit": units[channel],
                                      "value": value if math.isfinite(value) else None} for channel, value in values.items()]},
            "boundary": "Historical trigger snapshot and the saved rule revision used for this match. The snapshot alone does not prove the full persistence sequence or current equipment condition. Ingestion source is not established by this record."}


def create_rule_inbox_router():
    router = APIRouter(prefix="/api/condition-rules", tags=["Condition inbox"])

    @router.get("/inbox")
    def inbox(review_state: Literal["unreviewed", "acknowledged", "resolved", "all"] = "unreviewed",
              ownership: Literal["all", "mine", "unassigned"] = "all",
              investigation_state: Literal["all", "not_started", "awaiting_review", "approved", "approval_needed", "rejected", "dispatched", "unavailable"] = "all",
              site: str | None = Query(default=None, max_length=100),
              before_created: float | None = Query(default=None, ge=0, allow_inf_nan=False),
              before_id: str | None = Query(default=None, min_length=1, max_length=36),
              user: User = Depends(current_user), db: Session = Depends(get_db)):
        allow(user, "engineer", "admin")
        if site and site not in user.sites: raise HTTPException(403, "Site access is not permitted.")
        if (before_created is None) != (before_id is None): raise HTTPException(422, "Provide both cursor values or neither.")
        clock = now()
        latest_state = select(ConditionRuleReview.state).where(ConditionRuleReview.match_id == ConditionRuleMatch.id).order_by(ConditionRuleReview.version.desc()).limit(1).scalar_subquery()
        filters = [Asset.site.in_([site] if site else user.sites)]
        latest_owner = select(ConditionRuleAssignment.owner_id).where(ConditionRuleAssignment.match_id == ConditionRuleMatch.id).order_by(ConditionRuleAssignment.version.desc()).limit(1).scalar_subquery()
        if ownership == "mine": filters.append(latest_owner == user.id)
        if ownership == "unassigned": filters.append(latest_owner.is_(None))
        if review_state != "all": filters.append(func.coalesce(latest_state, "unreviewed") == review_state)
        link_exists = select(ConditionMatchInvestigation.match_id).where(ConditionMatchInvestigation.match_id == ConditionRuleMatch.id).exists()
        linked = select(Investigation.state).join(ConditionMatchInvestigation, ConditionMatchInvestigation.investigation_id == Investigation.id).where(
            ConditionMatchInvestigation.match_id == ConditionRuleMatch.id, Investigation.asset_id == Asset.id).correlate(ConditionRuleMatch, Asset)
        linked_state = linked.scalar_subquery()
        approval_valid = linked.with_only_columns(case((and_(Investigation.state == 'approved',
                    Investigation.approved_hash == Investigation.payload_hash, Investigation.approved_until >= clock), True), else_=False)).scalar_subquery()
        if investigation_state == 'not_started': filters.append(~link_exists)
        elif investigation_state == 'unavailable': filters.extend([link_exists, linked_state.is_(None)])
        elif investigation_state == 'approved': filters.extend([linked_state == 'approved', approval_valid == True])
        elif investigation_state == 'approval_needed': filters.extend([linked_state == 'approved', approval_valid == False])
        elif investigation_state != 'all': filters.append(linked_state == investigation_state)
        count = db.scalar(select(func.count()).select_from(ConditionRuleMatch)
                          .join(ConditionRule, ConditionRule.id == ConditionRuleMatch.rule_id)
                          .join(Asset, Asset.id == ConditionRule.asset_id).where(*filters))
        query = select(ConditionRuleMatch, ConditionRuleRevision, Asset).join(ConditionRule, ConditionRule.id == ConditionRuleMatch.rule_id)
        query = query.join(Asset, Asset.id == ConditionRule.asset_id).join(ConditionRuleRevision,
                  (ConditionRuleRevision.rule_id == ConditionRuleMatch.rule_id) & (ConditionRuleRevision.version == ConditionRuleMatch.rule_version)).where(*filters)
        if before_id is not None:
            query = query.where(or_(ConditionRuleMatch.created < before_created,
                                    and_(ConditionRuleMatch.created == before_created, ConditionRuleMatch.id < before_id)))
        rows = list(db.execute(query.order_by(ConditionRuleMatch.created.desc(), ConditionRuleMatch.id.desc()).limit(51)))
        items = [{"id": match.id, "name": revision.name, "rule_version": match.rule_version,
                  "asset_tag": asset.tag, "asset_name": asset.name, "site": asset.site,
                  "signal_state": match.state, "triggered_at": match.triggered_at, "ended_at": match.ended_at,
                  "created": match.created, "review": review_json(current_review(db, match.id))}
                 for match, revision, asset in rows[:50]]
        for item, (_, _, asset) in zip(items, rows[:50]):
            item['ownership'] = ownership_for(db, item['id'], asset.site_id)
            item['investigation'] = investigation_summary(db, item['id'], asset.id, clock)
        return {"items": items, "total_matching": count,
                "next_cursor": {"before_created": rows[49][0].created, "before_id": rows[49][0].id} if len(rows) > 50 else None,
                "boundary": "Local rule matches for permitted equipment. Signal state describes the last processed snapshot. This inbox sends no email or external notifications."}

    return router


def create_rule_review_router(asset_for, idempotent, finish):
    router = APIRouter(prefix="/api/condition-rules/matches", tags=["Rule match review"])

    def match_for(db, user, match_id):
        allow(user, "engineer", "admin")
        match = db.get(ConditionRuleMatch, match_id)
        if match is None: raise HTTPException(404, "Rule match not found.")
        rule = db.get(ConditionRule, match.rule_id)
        return match, asset_for(db, user, rule.asset_id)

    @router.get("/{match_id}/evidence")
    def evidence(match_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
        match, asset = match_for(db, user, match_id)
        return match_evidence(db, match, asset)

    @router.get("/{match_id}/export")
    def export(match_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
        from .rule_exports import export_match
        match, asset = match_for(db, user, match_id)
        return export_match(db, match, asset)

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
