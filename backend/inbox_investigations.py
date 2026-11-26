"""Permission-scoped inbox summaries, separate from captured investigation origins."""
from .database import ConditionMatchInvestigation, Investigation


def investigation_summary(db, match_id, asset_id, clock):
    link = db.get(ConditionMatchInvestigation, match_id)
    if link is None: return None
    inv = db.get(Investigation, link.investigation_id)
    if inv is None or inv.asset_id != asset_id:
        return {'state': 'unavailable'}
    return {'id': inv.id, 'title': inv.title, 'state': inv.state, 'version': inv.version,
            'approved_until': inv.approved_until,
            'approval_current': bool(inv.state == 'approved' and inv.approved_hash == inv.payload_hash
                                     and inv.approved_until is not None and inv.approved_until >= clock)}
