"""Read-only, permission-scoped condition review downloads."""
import json
from fastapi.responses import Response
from sqlalchemy import func, select
from .database import ConditionRuleReview, ConditionRuleAssignment, now
from .rule_assignments import assignment_json, eligible
from .inbox_investigations import investigation_summary

HISTORY_LIMIT = 100


def export_match(db, match, asset):
    # Import after the review router is initialized; no new authorization path.
    from .rule_reviews import match_evidence, review_json
    evidence = match_evidence(db, match, asset)
    clock = now()
    reviews = list(db.scalars(select(ConditionRuleReview).where(ConditionRuleReview.match_id == match.id)
                              .order_by(ConditionRuleReview.version.desc()).limit(HISTORY_LIMIT)))
    assignments = list(db.scalars(select(ConditionRuleAssignment).where(ConditionRuleAssignment.match_id == match.id)
                                  .order_by(ConditionRuleAssignment.version.desc()).limit(HISTORY_LIMIT)))
    review_total = db.scalar(select(func.count()).select_from(ConditionRuleReview).where(ConditionRuleReview.match_id == match.id))
    assignment_total = db.scalar(select(func.count()).select_from(ConditionRuleAssignment).where(ConditionRuleAssignment.match_id == match.id))
    owner = assignments[0] if assignments else None
    report = {
        'format': 'sentinel.condition-review', 'format_version': 1, 'generated_at': clock,
        'time_reference': 'Unix seconds, UTC; portal display uses Asia/Dubai (GST, UTC+4).',
        'evidence': evidence,
        'review': {'current': review_json(reviews[0] if reviews else None),
                   'history_newest_first': [review_json(row) for row in reviews],
                   'total_records': review_total, 'included_records': len(reviews), 'truncated': review_total > len(reviews)},
        'ownership': {'current': assignment_json(owner),
                      'owner_currently_eligible': bool(owner and owner.owner_id and eligible(db, owner.owner_id, asset.site_id)),
                      'history_newest_first': [assignment_json(row) for row in assignments],
                      'total_records': assignment_total, 'included_records': len(assignments), 'truncated': assignment_total > len(assignments)},
        'linked_investigation': investigation_summary(db, match.id, asset.id, clock),
        'scope': {'match_id': match.id, 'history_limit_per_section': HISTORY_LIMIT,
                  'excluded': ['Full investigation payload and approvals', 'Source-event sequence and provenance beyond the saved trigger',
                               'Work-order execution and physical maintenance evidence', 'Account credentials and private configuration']},
        'boundary': 'A read-only local record assembled at download time; live state may change during or after generation. '
                    'History sections include at most the 100 newest entries and explicitly report truncation. '
                    'A review, paused signal or linked investigation does not confirm a physical fault, repair or maintenance completion. '
                    'This file is not a signed certificate or a full system backup. Protect downloaded review notes and ownership details.',
    }
    return Response(json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2), media_type='application/json',
                    headers={'Content-Disposition': f'attachment; filename="sentinel-condition-{match.id}.json"',
                             'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
