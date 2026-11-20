# Phase 3, Step 5: rejected sensor data review

This increment adds an opt-in, bounded intake API and a per-sensor Data review tab. Original rejected JSON objects and their validation errors remain available after correction or dismissal. It extends the existing local reference application; Phase 3 is still partial.

## Install and manual acceptance

Prerequisite: Phase 3 Step 4 installed, revision 0005. Stop Sentinel with Ctrl+C, run Apply-Phase3Step5.ps1, restart scripts/run.py and refresh Ctrl+F5. The updater creates revision 0006 with checked code/database backups and preserves existing records and .env. No dependency install or whole-project replacement is required. The automatic installer is for SQLite; PostgreSQL needs a separately reviewed migration procedure.

1. Open Sensor registry > C-202 Temperature > Inspect events > Data review.
2. Click Create rejected-unit test. This deliberately submits value 212 with an unsupported unit, a current observation time and source manual-quarantine-test.
3. Confirm the item is Pending review and shows the unit rejection. Click Review item.
4. Keep corrected value 212. Select degF as the Verified original unit. Keep the original observation time and Good quality.
5. Enter a reason, such as: Correcting the intentional unit error in this Fahrenheit test.
6. Click Validate correction & replay. The item becomes Corrected & replayed, retaining the original payload, errors, reviewer reason, decision time and corrected event ID.
7. Open Sensor events to confirm the new quarantine-review event shows 212 degF converted to 100 degC. Reopen Data review and choose All statuses to verify evidence persists.
8. To test dismissal, create another labelled test, review it, enter a reason and click Dismiss with reason. It retains the original evidence without creating an event.

Corrections remain independent sensor events. They are not automatically published into equipment snapshots. Equipment alignment still requires four fresh, good-quality channels within its policy window. Preserve the real observation time; do not make old readings appear current to pass freshness checks.

## Intake API and boundaries

POST /api/sensor-intake/{sensor_id}, JSON {"raw_payload":{...event fields...}}, accepts an existing, authorized sensor identity. Event fields match the independent-event schema: message_id, observed_at (epoch seconds), raw_value, raw_unit, quality and source. sensor_id may be omitted inside the object; if supplied it must match the path. Role Engineer/Admin, authenticated session, CSRF and Idempotency-Key are required.

The envelope is strict. Raw payload must be a finite JSON object, at most 4096 bytes in the encoded representation, at most 16 top-level fields, and at most six nesting levels. Malformed/oversized/non-JSON-safe envelopes, identity mismatch, authentication/authorization failures and storage errors are rejected without quarantine. Within those bounds, event schema errors, unsupported units, out-of-range values, future timestamps and changed-content message conflicts are retained in quarantine. Source is caller-supplied, not a verified device identity.

Valid submissions use the same event validation, conversion, audit and duplicate logic as the existing sensor-events batch API. Response is outcome=accepted, event_id, duplicate, snapshot_projection=false. Validation failures return outcome=quarantined with the retained item and duplicate status; HTTP 201 indicates a persisted intake outcome, not necessarily an accepted measurement. Same-key replay returns its original response. Equivalent raw objects for the same sensor deduplicate by their sorted-JSON hash; an already resolved item is not reopened. Original evidence is a parsed JSON object, not an exact copy of HTTP bytes or whitespace.

Existing POST /api/sensor-events/batches retains its atomic all-or-nothing behavior. It does not automatically feed the quarantine queue. This release is not a broker dead-letter queue, parser sandbox, automatic retry worker or unbounded archive. The UI queue shows the latest 50 matching records; API maximum is 100 and full pagination is future work.

## Review APIs

GET /api/sensor-quarantine?sensor_id=<ID>&status=pending|replayed|dismissed|all&limit=50 returns scoped records and supported units. Permitted read-only roles can inspect evidence; only Engineer/Admin can intake, replay or dismiss.

POST /api/sensor-quarantine/{id}/replay accepts expected_version, raw_value, raw_unit, observed_at, quality and reason (10–1000 trimmed characters). It revalidates measurement fields, creates a new event with message_id quarantine:<item UUID> and source quarantine-review, then records corrected payload, reviewer, reason and resolution timestamp. Original raw payload and errors remain unchanged. The stable new message identity prevents overwriting an already accepted event with a corrected value.

POST /api/sensor-quarantine/{id}/dismiss accepts expected_version and reason. It preserves evidence and resolves the item without creating a sensor event. Neither endpoint supports deleting, reopening or editing a terminal review item.

Both mutations require CSRF and Idempotency-Key, check current canonical site permissions before replaying old responses, and use status/version compare-and-update to prevent competing resolutions. Event creation, status update, audit and idempotency receipt commit together; failures roll back all changes. Database constraints enforce sensor/user/event references, payload uniqueness, positive versions, allowed statuses and consistent terminal states. API validation errors omit raw input values from error responses, including invalid floating-point inputs.

## Verification

125 tests passed on SQLite and 125 on isolated PostgreSQL 18.6 under a non-superuser application role. Tests cover valid intake, invalid payload preservation, deduplication, content conflicts, corrected-event lineage, dismissal, status/version conflicts, CSRF, role/site access including idempotent replays, bounded input, non-finite JSON rejection, rollback, database constraints and revision 0005-to-0006 preservation. Existing workflow/alignment/event tests also passed after using a shared event-persistence helper.

Fresh/legacy migrations and metadata comparison passed. PostgreSQL logical dump/restore preserved the tested quarantine rows, corrected events, snapshots and projection history. TypeScript and Vite production build passed. One existing Starlette test-client deprecation warning remains. Browser interaction for this increment was not verified because local browser access was disabled; complete the installed-app walkthrough above. No production throughput, plant deployment or device/broker integration is claimed.

## Next work

Retention/partitioning, complete queue pagination, reviewed recovery objectives, durable streaming ingestion, device identity and live PostgreSQL cutover remain Phase 3 work. Enterprise identity, evaluated models/retrieval, real vendor integrations and industrial pilot acceptance remain separate milestones.
