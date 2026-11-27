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

Exact match pages also provide a permission-scoped JSON review download with the saved trigger evidence, current review/ownership states, bounded history with explicit omission flags and a linked-investigation summary. It is a local readout, not a signed certificate, atomic snapshot or system backup. See CONDITION_REVIEW_EXPORT.md.

Work remaining includes approved external notification routing/delivery/retries/escalation and maintenance suppression; representative real-source integration and outage behavior; job/resource/parts and field/return-to-service evidence; a vendor CMMS connection; agreed downtime/reliability/report calculations; selected production identity, hosting, storage/retention and durable processing; monitoring, off-machine backups, recovery/load/security acceptance; named pilot owners, training and rollout sign-off. Optional deployment choices remain subject to agreed scope.

This page is a manually reviewed development map, dated with the build. It does not read private configuration, inspect credentials, enroll accounts, approve the simulation draft, connect equipment or start maintenance. Historical increment documents retain their original as-of descriptions; this snapshot summarizes later delivered work. Future increments should update this map when their implementation and evidence are available.

This update changes frontend copy/data and layout only. Database schema remains 0016; runtime accounts, MFA, readings, rules, matches, reviews, ownership and investigations are preserved. Installation backs up checked source/build files and retains older hashed assets for already-open clients. The existing split-page loading design remains in use.
