# Phase 3, Step 1: sensor identity and freshness

## Implemented

The Sensor registry page exposes one permanent UUID per equipment/channel. Existing
assets are backfilled with vibration (mm/s), temperature (degC), pressure (bar)
and flow (m3/h). UUIDs are deterministic from the immutable asset ID and channel;
labels, reporting expectations and restarts do not change them. Registering new
equipment creates its four channel identities in the same transaction.

Engineer/Admin can edit label, expected reporting interval and the stale-after
limit. Edits require CSRF, site permission and expected configuration version;
stale updates return 409. Units and equipment association are immutable through
this API. Changes create audit events. Database foreign keys, unique asset/channel
keys and CHECK constraints enforce registry consistency.

Sample quality and freshness are independent. The registry uses each sensor's
configured stale-after limit. The existing equipment-condition engine continues
to use its one-hour freshness rule; the configuration form explicitly states this.
The Live monitoring card now shows full date, age, and equipment freshness rather
than showing an unqualified Good quality message for old samples.

## API

- GET /api/sensors?site=...&asset_id=... : permitted registry and summary.
- PATCH /api/sensors/{id} : label, expected_interval_seconds,
  stale_after_seconds and expected_version; Engineer/Admin only.

Values still map from the existing four-channel equipment snapshots. Independent
per-sensor ingestion and unit conversion are NOT implemented in this increment.
Site authorization still derives from the existing asset/site association; stable
site UUIDs and database-level tenant isolation remain further work.

## Checked local SQLite upgrade

Stop Sentinel before applying the update. The installer refuses an occupied
server port, validates checksums, backs up replaced files, runs schema preflight
and applies scripts/upgrade_sensor_registry.py. That script:

1. Validates the expected existing schema and migration history.
2. Uses metadata comparison before adopting an unversioned legacy database.
3. Creates and integrity-checks an online SQLite backup.
4. Applies Alembic revision 0002 and backfills stable IDs.
5. Writes a local upgrade report with table counts and backup location.
6. Restores the original database if the upgrade fails after backup.

The installer restores application files if the upgrade fails. No existing
passwords or readings are transformed. PostgreSQL automatic upgrade is explicitly
refused; a separate PostgreSQL validation increment is still required. Existing
local create_all installations and revision-0001 installations were both tested.
Repeated upgrade preserves IDs and configuration.

## Verification

59 tests passed: existing application behavior, six registry tests and six upgrade
cases. Coverage includes site/role isolation, CSRF, immutable units, optimistic
concurrency, unique keys, FK/CHECK rejection, stable IDs, new-asset mapping, quality
versus freshness, legacy adoption, schema drift refusal, repeat upgrade, failed
upgrade recovery and occupied-server refusal. TypeScript/production build passed.
The source-copy UI was checked for search and configuration saving. Actual
installed user data was not used in the tests.

## Next increments

- Step 2: PostgreSQL verification and stable site identity/relational isolation.
- Step 3: normalized per-sensor events and validated unit handling.
- Step 4: durable ingestion, quarantine and broker replay.
- Step 5: outage, capacity and recovery acceptance evidence.

Phase 3 remains PARTIAL. Completing this step does not imply production readiness.

The desktop and phone configuration layouts were also inspected; table overflow
is contained in horizontal scrolling. The complete PowerShell installer was run
on an isolated older source copy: it preserved password hashes and reading counts.
An injected schema difference was rejected and the previous application files
were restored.
