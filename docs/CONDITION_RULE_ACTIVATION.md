# Condition management, increment 3: controlled activation and snapshot-driven evaluation

Saved rule drafts remain inactive by default. An administrator loads a draft, reviews the immutable saved settings in **Controlled activation**, supplies a reason and review confirmation, and activates that exact saved revision. Saving another draft revision does not replace a running revision. Activate it separately after reviewing it. Administrators can pause a rule; pausing closes an active match with state paused and resets pending persistence. Engineers may preview, save drafts and read activation/match history, but cannot activate or pause rules.

Activation and pause use current site authorization, session/MFA policy, CSRF/origin checks, idempotency receipts, a draft-head version check and a control-state version check. Concurrent control operations serialize per equipment item. Concurrent snapshot evaluation uses a separate compare-and-swap evaluation version. An evaluation conflict rolls back the whole incoming transaction so the sender can retry the same request identity. Editing a draft never silently retargets an active deployment. This local build permits at most 20 active rules per asset.

## New observations only

Activation records the current time and the latest existing snapshot timestamp as a watermark. It does not evaluate stored history or create a match during activation. Only subsequently accepted equipment snapshots newer than both boundaries are eligible. Independent sensor events still need the existing reviewed alignment/publication workflow. Manual snapshot intake, published projections and demo replay all use the shared evaluator hook. Bad/suspect snapshots interrupt continuity; older/out-of-order observations do not backfill rule state. Exact message retries retain the existing ingestion deduplication guarantees.

The evaluator triggers after good finite observations remain strictly above the saved threshold for the persistence duration. It clears at or below threshold minus clear margin. Gaps greater than the configured maximum end an existing match as data_gap, then begin fresh persistence with the next observation. Invalid samples end a match as invalid_sample. No interpolation is assumed. Replacing an active revision closes its active match as replaced and starts fresh persistence. Zero persistence triggers on the first eligible observation above the limit.

State is stored transactionally in SQLite/PostgreSQL models and survives application restart. There is no independent scheduler in this increment: elapsed time or a connection outage alone does not trigger/clear a record. A gap is processed when the next snapshot arrives. An active record describes the last evaluated snapshot, not guaranteed present equipment condition. The status panel reports the last actually evaluated observation; its initial watermark is not misreported as evaluated data.

## Matches, audit and limits

The panel lists the latest 100 rule matches for the selected equipment. Each match retains rule/revision identity, start/trigger/end observations, state and original trigger-reading ID. Trigger, clear, interruption, pause and replacement generate audit records. Historical settings remain available from the immutable application revision history. No physical diagnosis, failure probability, automatic maintenance approval or plant control is performed.

Existing demonstration-score condition episodes remain separate from these rule-match records. This increment does not generate work orders, send email, deliver notifications or dispatch to a vendor CMMS. Notification routing, escalation, suppression, durable distributed workers, acknowledgement/resolution workflows, incident support, performance review and representative engineering validation remain future work.

## Upgrade

Migration 0013 adds condition_rule_deployments and condition_rule_matches. Existing drafts, revision history, accounts, enrolled MFA, policy and readings remain unchanged. No existing rule is activated by migration. The installer backs up source files and the SQLite database, checks stopped-server/schema/source prerequisites, restores the database/source on failure, and resumes the existing GitHub source watcher using a single Git executable path. The private MFA key and environment configuration are excluded.

API: GET /api/condition-rules/drafts/{id}/deployment; POST /drafts/{id}/control with action, expected_version, expected_rule_version, reason and confirmed=true; GET /activity?asset_id=... for bounded match history. Existing draft and preview endpoints retain their purpose. Draft API properties describe draft storage; deployment state is authoritative for running rules.

Only synthetic fixtures are activated during automated verification. Activation of a real installed rule is an explicit administrator action after installation. This is still a local reference application, not a completed industrial production deployment.
