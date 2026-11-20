# Phase 3, Step 3: independent sensor events

This increment adds persistent per-sensor events, explicit unit normalization and an inspection interface. It is ready for local demonstration and integration development; it does not connect plant equipment.

## Installation

Stop Sentinel with Ctrl+C. Run Apply-Phase3Step3.ps1 against the existing project, restart scripts/run.py, and refresh with Ctrl+F5. Open Sensor registry > Inspect events. No dependency installation is required. The checked SQLite upgrade creates revision 0004, backs up the database, and preserves accounts, passwords, snapshots, sensor IDs and site memberships. Schema drift or an occupied server port stops installation. Code files are backed up separately and restored if installation fails. Do not apply an older updater after this release. PostgreSQL installations require a separate migration procedure; this installer refuses automatic PostgreSQL changes.

## Operator walkthrough

1. Sign in as Engineer or Admin and open Sensor registry.
2. Choose Inspect events beside a temperature sensor.
3. Enter 212, select degF, keep an appropriate observed time and quality, then Validate & save event.
4. The event history shows 212 degF converted to 100 degC, with event/message IDs, observation/receipt times and source manual-ui.
5. Refresh or reopen the inspector to verify persistence. Technician and other permitted roles can inspect events but cannot submit them.

## API contract

GET /api/sensor-events?sensor_id=<registered-ID>&limit=50 returns latest independent events, ordered by observation time, receipt time and event ID descending. Limit is 1–200. History is bounded, not a full export or cursor-paginated archive.

POST /api/sensor-events/batches accepts JSON {"records":[{"sensor_id":"<registered-ID>","message_id":"gateway-unique-message-ID","observed_at":1793437200,"raw_value":212,"raw_unit":"degF","quality":"good","source":"gateway-demo"}]}. Use a current observation timestamp for a live test. Authentication cookie, X-CSRF-Token and Idempotency-Key (8–100 characters) are required. Records: 1–500. Quality: good/suspect/bad. Unknown fields, blank strings, non-finite numbers, non-positive timestamps, timestamps more than 120 seconds ahead and values outside canonical bounds are rejected. Older observations are accepted and remain historical.

Response: inserted, duplicates, event_ids (input order), snapshot_projection=false. The batch is atomic, including its audit records. A repeated (sensor_id,message_id) with identical submitted content returns the existing event without another audit record. Changed content returns 409 and saves none of the batch. A request-key replay returns its original response; current sensor/site permissions are checked first. Concurrent uniqueness conflicts return 409 for retry. Message IDs must be coordinated across producers for each sensor. Source is a caller-supplied provenance label, not a verified device identity.

Each event stores raw value/unit, canonical value/unit, observed_at, server received_at, quality, source, message ID, event UUID and conversion version units-v1. Existing events have no mutation endpoint. Server permissions follow canonical site memberships through the sensor's asset. Database constraints cover sensor FK, message uniqueness, positive timestamps and quality; dimensional conversion and ranges are enforced by the API.

## Supported units

| Channel | Canonical / range | Accepted inputs |
|---|---|---|
| Vibration | mm/s, 0–200 | mm/s; in/s ×25.4; m/s ×1000 |
| Temperature | degC, −100–500 | degC; (degF−32)×5/9; K−273.15 |
| Pressure | bar, 0–1000 | bar; kPa ÷100; MPa ×10; psi ×0.06894757293168 |
| Flow | m3/h, 0–100000 | m3/h; L/min ×0.06; m3/s ×3600; L/s ×3.6 |

These broad demonstration ranges are software acceptance bounds, not calibrated equipment limits or alarm thresholds. Floating-point conversions retain stored precision; the interface rounds for readability.

## Compatibility and boundaries

Legacy POST /api/telemetry/batches and demo replay retain their complete four-channel snapshot behavior. The registry table explicitly shows snapshot values/freshness. Independent events are visible in the inspector and do not update equipment health, ML, alarms or existing snapshot history. No missing channels are invented or stitched into a synthetic simultaneous reading. No historical events are fabricated during migration.

Still pending: synchronized snapshot projection with explicit time alignment, quarantine/reprocessing, retention/partitioning, broker ingestion with device identity, dead-letter handling and production throughput tests. MQTT/Kafka, live PostgreSQL cutover, industrial validation, SSO and vendor CMMS remain separate work. Phase 3 remains partial.

## Verification

91 tests passed on SQLite and the same 91 passed on isolated PostgreSQL 18.6 using a non-superuser application role. Coverage includes unit conversions, dimensions/ranges, finite values, timestamps, atomic rollback, duplicates/content conflicts, authorization, CSRF, site access on replay, event constraints, legacy upgrades, metadata agreement and migration failure restoration. PostgreSQL fresh/legacy migrations and a pg_dump/restore round trip preserved a normalized event and legacy rows. TypeScript and production build passed. Browser inspection verified 212 degF → 100 degC persists after reload and the form fits a 390px viewport; history tables scroll horizontally within the dialog. One existing Starlette test-client deprecation warning remains.
