# Condition management, increment 1: historical rule preview

Workspace settings > Condition rules is available to administrators and engineers. Select permitted equipment, a signal, a high limit, a clear margin, a persistence duration and a maximum observation gap. Preview evaluates the latest 500 stored equipment snapshots in observation-time order. More than 500 readings produces an explicit truncation notice.

This is a preview, not a saved or active alert rule. It does not alter asset thresholds, health scores, condition episodes, review decisions or notifications. Historical matches do not establish present equipment condition. Existing episode generation continues to use the prior demonstration scoring logic. Rule activation, rule versioning/audit, routing, suppression and escalation remain later increments.

## Evaluation semantics

- Only good-quality finite values count. Bad or suspect quality resets pending persistence and ends any active match at the last observation. No continuity is assumed through an invalid reading.
- A match triggers when observations remain strictly above the limit for at least the chosen persistence duration. Zero persistence triggers on the first observation above the limit.
- Before triggering, a reading at or below the limit resets the pending run. After triggering, a match clears at or below **limit minus clear margin**. Values between that clear level and the trigger limit preserve an active match.
- An observation gap greater than the configured maximum, or a duplicate timestamp, breaks continuity. A gap ends an active match at the last observation rather than claiming the actual condition cleared.
- No interpolation is performed, and the evaluator assumes no duration beyond the last sample. An open match at the end means active at the final historical observation only. A truncated window can omit an earlier trigger; results are bounded evidence, not a complete fleet report.
- Suggested signal limits are demonstration examples. They are not engineering recommendations. This first increment supports high-limit rules only and evaluates equipment snapshots, not independent sensor events. Events appear only after the existing reviewed alignment/publication workflow.

## Access and API

POST /api/condition-rules/preview uses the existing cookie session, CSRF/origin validation, administrator/engineer role checks and canonical site membership. The request has asset_id, channel, threshold, hysteresis, persistence_seconds and maximum_gap_seconds. Unknown fields, nonfinite settings and out-of-range values are rejected. The response states preview_only=true and saved=false. No database migration is needed; schema remains 0011.

## Installation and verification

Stop Sentinel, install the checked package, restart scripts/run.py and refresh the browser. The updater backs up affected source/build files, rejects unexpected local edits, pauses the existing source-sync helper during file installation, and resumes it afterward. It does not touch private account data, environment configuration or the MFA key.

Thirteen added backend tests cover persistence, hysteresis, boundary equality, bad/suspect quality, long gaps, duplicate timestamps, nonfinite values, empty/single-sample history, the 500-sample bound, no database mutation, role/site isolation, CSRF and invalid requests. Browser acceptance after installation remains pending. This increment does not complete the wider condition-management phase.
