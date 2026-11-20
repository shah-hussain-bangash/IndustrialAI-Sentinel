# Reliability Lab

The **Reliability lab** navigation item adds three working tools and a scoped CSV brief.

## Fleet triage

Choose a site and a 24-hour, 7-day or 30-day data window. The queue shows quality
coverage, sample counts, latest-reading age, unresolved episodes and overdue work.
Click **Explain score** for the individual contributions, or the asset tag to open
its equipment details. Export brief downloads a CSV with the same site/window.

Triage method `triage-v1` sums:
- Condition: round((100 - condition index) * 0.4), capped by the existing index.
- Criticality: Critical 20, High 15, Medium 8, Low 3.
- Unresolved episodes: 10 each, capped at 20.
- Overdue open work: 10 each, capped at 20; date boundaries use GST.

Scores of 65+ are Urgent, 35+ Review soon, otherwise Routine. Assets without a
current good-quality condition index enter Data review, sorted first. Their
condition contribution is explicitly unavailable/zero, not an assumption of health.
The score is a transparent sorting heuristic, not failure probability.

## Compare assets

Select one to three permitted assets and one of four channels. The chart uses
shared actual time and value axes. Up to the latest 300 recorded samples per asset
are retrieved within the window. Statistics and curves exclude non-good quality
readings. Historical slope is calculated using elapsed hours, not sample index.
It is not a forecast. Constant values in the last 12 good readings trigger an
inspection note rather than an automatic sensor-failure diagnosis. Lines connect
retained good samples; absent intervals are not measurements.

## Scenario lab

Choose equipment with a good-quality reading. Edit hypothetical vibration,
temperature, pressure and flow and click Run what-if scenario. This compares the
existing condition heuristic and synthetic anomaly detector against that exact
baseline. Stale baselines carry a visible historical-data notice. Scenario runs
never write sensor readings, change thresholds, control equipment or create work
orders. This is not a calibrated digital twin, RUL model or physical degradation
simulation.

Engineer and Admin may name and save a run. It is persisted as a Scenario saved
audit event, with title, actor, original baseline, inputs, result, time, method
and model version. The latest 25 saved runs are visible per permitted site and can
be inspected without recomputing historical results. Save commands use scoped
idempotency keys. A SHA-256 fingerprint plus timestamp rejects a baseline that
changed after the user loaded it, including value changes at the same timestamp.

## API and permissions

All endpoints require an existing authenticated session and site authorization:
- GET /api/lab/fleet?hours=168&site=...
- GET /api/lab/export.csv?hours=168&site=...
- GET /api/lab/compare?ids=...&ids=...&hours=168
- POST /api/lab/simulate (CSRF required)
- POST /api/lab/scenarios (Engineer/Admin, CSRF and Idempotency-Key required)
- GET /api/lab/scenarios?site=...

The router is in backend/reliability.py, mounted before the SPA fallback. The
interface is src/pages/ReliabilityPage.tsx. Existing SQLite audit and idempotency
tables are reused, so no schema migration or dependency change is required.
Password hashes and account sessions are not migrated or reset by installation.

## Verification and limits

47 backend tests passed, including 13 Reliability Lab cases covering permissions,
CSRF, site isolation, bounds, stale/bad data, scoring, bounded comparisons, slopes,
constant-value checks, unchanged telemetry, baseline consistency, idempotency,
audit storage and CSV formula escaping. TypeScript and production build passed.
Desktop/phone layouts, scoring explanations, three-asset selection, scenario
calculation, saving and opening history were reviewed through the interface.
One existing Starlette TestClient deprecation warning remains.

This is a local reference implementation with synthetic seed data. Large-fleet
query optimization, distributed rate limits, industrial model calibration and
vendor integrations remain separate implementation and validation work.
