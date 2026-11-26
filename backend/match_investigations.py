"""Link rule matches to the existing independently reviewed recommendation workflow."""
import math
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from .database import (ConditionMatchInvestigation, ConditionRuleMatch, ConditionRule, Investigation,
                       RecommendationRevision, Document, User, Audit, now)
from .security import allow, current_user, get_db
from .rule_reviews import match_evidence
from .intelligence import make_investigation
from .seed import payload_hash


class MatchInvestigationCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(default='', max_length=200)
    reason: str = Field(min_length=5, max_length=1000)

    @field_validator('title', 'reason')
    @classmethod
    def clean_text(cls, value, info):
        value = value.strip()
        if any(ord(c) < 32 for c in value) or (info.field_name == 'reason' and len(value) < 5):
            raise ValueError('Provide a title without control characters and an investigation note of at least five characters.')
        return value


def fresh_snapshot(reading):
    return (reading is not None and reading.quality == 'good' and math.isfinite(reading.timestamp)
            and -300 <= now() - reading.timestamp <= 3600
            and all(math.isfinite(getattr(reading, channel)) for channel in ('vibration', 'temperature', 'pressure', 'flow')))


def create_match_investigation_router(asset_for, idempotent, finish, inv_json, latest):
    router = APIRouter(prefix='/api/condition-rules/matches', tags=['Condition investigations'])

    def match_for(db, user, match_id):
        allow(user, 'engineer', 'admin')
        match = db.get(ConditionRuleMatch, match_id)
        if match is None: raise HTTPException(404, 'Rule match not found.')
        rule = db.get(ConditionRule, match.rule_id)
        return match, asset_for(db, user, rule.asset_id)

    def linked(db, match, asset):
        link = db.get(ConditionMatchInvestigation, match.id)
        if link is None: return None
        inv = db.get(Investigation, link.investigation_id)
        if inv is None or inv.asset_id != asset.id:
            raise HTTPException(409, 'The linked investigation is inconsistent. Ask an administrator to check the record.')
        return inv

    @router.get('/{match_id}/investigation')
    def status(match_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
        match, asset = match_for(db, user, match_id)
        inv = linked(db, match, asset)
        ready = fresh_snapshot(latest(db, asset.id)) if inv is None else False
        return {'investigation': inv_json(db, inv) if inv else None, 'ready': ready,
                'message': 'A linked investigation already exists.' if inv else
                    ('Fresh telemetry is available. Preparing an investigation still requires independent review before action.' if ready else
                     'Fresh, good-quality telemetry is required. Replay or ingest a current sample, then reload investigation status.')}

    @router.post('/{match_id}/investigation', status_code=201)
    def prepare(match_id: str, body: MatchInvestigationCommand, request: Request,
                user: User = Depends(current_user), db: Session = Depends(get_db)):
        match, asset = match_for(db, user, match_id)
        key, digest, receipt = idempotent(db, request, user, body.model_dump())
        if receipt is not None: return receipt
        # Match identity is the single creation boundary even when callers use different keys.
        db.execute(update(ConditionRuleMatch).where(ConditionRuleMatch.id == match_id).values(state=ConditionRuleMatch.state))
        db.refresh(match)
        # Another request with this key may have committed while the match lock was awaited.
        key, digest, receipt = idempotent(db, request, user, body.model_dump())
        if receipt is not None: return receipt
        inv = linked(db, match, asset)
        if inv is not None:
            return finish(db, key, digest, {'investigation': inv_json(db, inv), 'created': False})
        reading = latest(db, asset.id)
        if not fresh_snapshot(reading):
            raise HTTPException(409, 'Fresh, good-quality telemetry is required. Replay or ingest a current sample first.')
        origin = match_evidence(db, match, asset)
        units = {'vibration': 'mm/s', 'temperature': '°C', 'pressure': 'bar', 'flow': 'm³/h'}
        origin['analysis_snapshot'] = {'id': reading.id, 'timestamp': reading.timestamp, 'quality': reading.quality,
             'signals': [{'channel': channel, 'unit': unit, 'value': getattr(reading, channel)} for channel, unit in units.items()]}
        origin['prepared_at'] = now()
        origin['investigation_note'] = body.reason
        docs = list(db.scalars(select(Document).where(Document.site == asset.site)))
        payload = make_investigation(asset, reading, docs)
        payload['condition_origin'] = origin
        payload['observations'].insert(0, f"Prepared from condition match {match.id}, saved rule revision {match.rule_version}. Analysis uses the separately identified fresh snapshot, not an assumption that the historical trigger is still active.")
        payload['data_gaps'].append('The condition trigger is historical. Its snapshot alone does not establish the full persistence sequence, ingestion source or current physical fault.')
        inv = Investigation(asset_id=asset.id, creator_id=user.id, title=body.title or f'Condition match · {asset.tag} · {origin["rule"]["name"]}',
                            payload=payload, payload_hash=payload_hash(payload))
        db.add(inv); db.flush()
        db.add(RecommendationRevision(investigation_id=inv.id, version=1, actor_id=user.id, payload=payload, payload_hash=inv.payload_hash))
        db.add(ConditionMatchInvestigation(match_id=match.id, investigation_id=inv.id))
        db.add(Audit(site=asset.site, actor=user.name, action='Condition investigation prepared', target=asset.tag,
                     details=f'Match {match.id}; investigation {inv.id}; rule revision {match.rule_version}; trigger reading {match.trigger_reading_id}; analysis reading {reading.id}. Note: {body.reason}. Awaiting independent review; no dispatch or review-state change.'))
        db.flush()
        return finish(db, key, digest, {'investigation': inv_json(db, inv), 'created': True})

    return router
