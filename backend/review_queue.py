"""Scoped review search and signed, expiring keyset pagination."""
import base64
import hashlib
import hmac
import json
import secrets
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator
from sqlalchemy import String, and_, cast, func, or_, select

from .database import SensorQuarantine, now

# Cursors are short-lived navigation tokens for this single-process reference app.
# Restarting the process invalidates them; no persistent secret or .env change needed.
_CURSOR_SECRET = secrets.token_bytes(32)
CURSOR_SECONDS = 900


class Cursor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    user_id: str = Field(min_length=1, max_length=36)
    sensor_id: str = Field(min_length=1, max_length=36)
    status: Literal["pending", "replayed", "dismissed", "all"]
    query: str = Field(max_length=100)
    limit: int = Field(ge=1, le=100)
    snapshot_at: FiniteFloat = Field(gt=0)
    expires_at: FiniteFloat = Field(gt=0)
    after_created: FiniteFloat | None = Field(default=None, gt=0)
    after_id: str | None = Field(default=None, min_length=1, max_length=36)

    @model_validator(mode="after")
    def paired_position(self):
        if (self.after_created is None) != (self.after_id is None):
            raise ValueError("Cursor position must be complete.")
        if self.after_created is not None and self.after_created > self.snapshot_at:
            raise ValueError("Cursor position is outside the result boundary.")
        return self


def encode(state):
    payload = base64.urlsafe_b64encode(state.model_dump_json().encode()).decode().rstrip("=")
    signature = hmac.new(_CURSOR_SECRET, payload.encode(), hashlib.sha256).hexdigest()
    return payload+"."+signature


def decode(token, bindings):
    try:
        if len(token) > 2048: raise ValueError("Cursor too long")
        payload, signature = token.split(".")
        expected = hmac.new(_CURSOR_SECRET, payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected): raise ValueError("Signature mismatch")
        state = Cursor.model_validate_json(base64.urlsafe_b64decode(payload+"="*(-len(payload)%4)))
        if state.expires_at <= now() or any(getattr(state,k) != v for k,v in bindings.items()):
            raise ValueError("Expired or different filters")
        return state
    except (ValueError, TypeError, UnicodeError):
        raise HTTPException(422, "Review queue cursor is invalid or expired. Refresh queue to restart browsing.")


def queue_page(db, user, sensor, status, query, limit, cursor, serialize):
    query = query.strip()
    bindings = {"user_id":user.id,"sensor_id":sensor.id,"status":status,"query":query,"limit":limit}
    clock = now()
    state = decode(cursor,bindings) if cursor else Cursor(**bindings,snapshot_at=clock,expires_at=clock+CURSOR_SECONDS)
    filters = [SensorQuarantine.sensor_id==sensor.id, SensorQuarantine.created<=state.snapshot_at]
    if query:
        fields = [SensorQuarantine.id,cast(SensorQuarantine.raw_payload,String),cast(SensorQuarantine.validation_errors,String),SensorQuarantine.review_reason,SensorQuarantine.corrected_event_id,cast(SensorQuarantine.corrected_payload,String)]
        filters.append(or_(*(field.icontains(query,autoescape=True) for field in fields)))
    grouped = db.execute(select(SensorQuarantine.status,func.count()).where(*filters).group_by(SensorQuarantine.status)).all()
    summary = {"pending":0,"replayed":0,"dismissed":0,**dict(grouped)}
    if status != "all": filters.append(SensorQuarantine.status==status)
    total = sum(summary.values()) if status=="all" else summary[status]
    if state.after_created is not None:
        filters.append(or_(SensorQuarantine.created<state.after_created,and_(SensorQuarantine.created==state.after_created,SensorQuarantine.id<state.after_id)))
    rows = db.scalars(select(SensorQuarantine).where(*filters).order_by(SensorQuarantine.created.desc(),SensorQuarantine.id.desc()).limit(limit+1)).all()
    visible = rows[:limit]
    next_cursor = None
    if len(rows)>limit:
        tail = visible[-1]
        next_cursor = encode(state.model_copy(update={"after_created":tail.created,"after_id":tail.id}))
    return {"items":[serialize(item) for item in visible],"summary":summary,"total_matching":total,
            "page_cursor":encode(state),"next_cursor":next_cursor,"snapshot_at":state.snapshot_at,
            "cursor_expires_at":state.expires_at,"limit":limit,"query":query,
            "ordering":"created descending, id descending", "status_updates":"live; refresh includes newer submissions"}
