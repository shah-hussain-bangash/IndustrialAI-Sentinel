# Development status snapshot — 27 November 2026

Production workspace > Development phases now describes the local build's implemented work, remaining scope and acceptance requirement for each of the ten existing development phases. Status labels mean Local workflow available, Partly implemented or Planned. They do not certify production readiness, imply that a whole phase is complete, or provide a live configuration/security assessment. Pilot and production rollout remain planned. No percentage-complete estimate is used.

The module catalog now recognizes delivered team/site access, invitation and recovery email, administrator authenticator MFA, condition rules/reviews/ownership, captured match evidence, linked investigations, investigation-status filters, basic work-order planning and local exports. It distinguishes account email from planned operational alert notifications, and a local CMMS simulator from a vendor connection. Links open the appropriate existing workspace; its role/site permissions still apply.

Implementation evidence reviewed for this snapshot:

| Area | Source and existing verification |
| --- | --- |
| Company and hierarchy | backend/foundation.py, backend/sites.py; organization/hierarchy and canonical site-access tests |
| Accounts and MFA | backend/team.py, backend/accounts.py, backend/mfa.py; role/site, session, invitation/recovery and MFA tests |
| Data foundation | backend/gateways.py, backend/sensor_events.py, backend/projections.py, backend/quarantine.py; synthetic ingestion and quality checks |
| Conditions | backend/condition_rules.py, backend/live_rules.py, backend/rule_reviews.py, backend/rule_assignments.py; rule/revision/evaluation/review/ownership tests and synthetic browser acceptance |
| Captured investigations | backend/match_investigations.py, backend/inbox_investigations.py; duplicate protection, captured evidence, approval guards and status-filter tests |
| Maintenance reference flow | backend/main.py and work-order workflow tests; independent version-bound approval, planning, local simulator submission and reconciliation |
| Local recovery and loading | backend/recovery.py; isolated restore verification; WorkspaceTool loading/recovery harness and startup dependency-graph checks |

The header attention panel now checks unreviewed saved rule matches inside the portal and opens exact, bookmarkable match-review records within permitted site access. Demonstration episodes remain separate. The panel checks on open or explicit refresh; it is not a push or outbound delivery system.

Exact match pages also provide permission-scoped JSON and printable HTML review downloads with the saved trigger evidence, current review/ownership states, bounded history with explicit omission flags and a linked-investigation summary. The readable HTML can be printed or saved as PDF through the browser. These are local readouts, not signed certificates, atomic snapshots or system backups. See CONDITION_REVIEW_EXPORT.md and PRINTABLE_CONDITION_REVIEW.md.

Equipment-scoped maintenance-window drafts now preserve proposed GST intervals and immutable revision history with role/site, CSRF, idempotency and stale-edit checks. They are inactive plans and do not affect rule evaluation. Independent administrator planning review now binds approval or rejection to the exact saved revision; editing invalidates its current decision while retaining review history. Controlled activation/cancellation of approved future windows now suppresses new saved-rule matches within an explicit equipment interval; readings and existing matches/reviews remain available. See MAINTENANCE_WINDOW_CONTROL.md. See MAINTENANCE_WINDOW_DRAFTS.md.

Inactive exact-rule notification plans now preserve planned site reviewers and provide captured-match previews with current eligibility checks, without sending or queueing email. See NOTIFICATION_PLAN_DRAFTS.md.

Work remaining includes approved activation of external notification routing/delivery/retries/escalation and real operating acceptance of maintenance suppression; representative real-source integration and outage behavior; job/resource/parts and field/return-to-service evidence; a vendor CMMS connection; agreed downtime/reliability/report calculations; selected production identity, hosting, storage/retention and durable processing; monitoring, off-machine backups, recovery/load/security acceptance; named pilot owners, training and rollout sign-off. Optional deployment choices remain subject to agreed scope.

This page is a manually reviewed development map, dated with the build. It does not read private configuration, inspect credentials, enroll accounts, approve the simulation draft, connect equipment or start maintenance. Historical increment documents retain their original as-of descriptions; this snapshot summarizes later delivered work. Future increments should update this map when their implementation and evidence are available.

The latest planning increment adds schema 0020's inactive notification-plan revision table, following the maintenance control/evidence tables with a checked, backed-up upgrade. Existing runtime accounts, MFA, readings, rules, matches, reviews, ownership and investigations are preserved. Installation backs up checked source/build files and retains older hashed assets for already-open clients. The existing split-page loading design remains in use.
