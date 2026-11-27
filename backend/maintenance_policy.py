"""Bounded snapshot policy. No scheduler, plant control, or review resolution."""
from sqlalchemy import select
from sqlalchemy.orm import aliased
from .database import MaintenanceWindowControl as Control, MaintenanceWindowDraft as Draft, MaintenanceWindowRevision as Revision

SCOPE = "Suppresses new saved-condition-rule matches for this equipment only. Readings are retained; existing matches still follow normal clearance/quality/gap processing. Reviews, demonstration episodes, notifications and physical work are unchanged. Status is measured at the stated server time."


def locked(db, draft_id):
    return db.get(Control, (draft_id, 1)) is not None


def state(db, draft_id, clock):
    activation = db.get(Control, (draft_id, 1))
    if not activation: return "inactive"
    if db.get(Control, (draft_id, 2)): return "cancelled"
    revision = db.get(Revision, (draft_id, activation.draft_version))
    if clock >= revision.ends_at: return "expired"
    return "scheduled" if clock < revision.starts_at else "suppressing"


def intervals(db, asset_id):
    cancellation = aliased(Control)
    rows = db.execute(select(Control, Revision, cancellation)
        .join(Draft, Draft.id == Control.draft_id)
        .join(Revision, (Revision.draft_id == Control.draft_id) & (Revision.version == Control.draft_version))
        .outerjoin(cancellation, (cancellation.draft_id == Control.draft_id) & (cancellation.version == 2))
        .where(Draft.asset_id == asset_id, Control.version == 1)).all()
    return [(a.draft_id, max(r.starts_at, a.created), min(r.ends_at, c.created if c else r.ends_at)) for a, r, c in rows]


def suppression_for(windows, observed, clock):
    return next((draft_id for draft_id, start, end in windows if start <= clock < end and start <= observed < end), None)


def crosses_window(windows, previous, observed):
    # A missing sample inside the window must not carry pre-window persistence across it.
    return any(start < end and previous < end and observed >= start and observed > previous for _, start, end in windows)
