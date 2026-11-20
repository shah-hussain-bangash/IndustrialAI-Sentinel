# Phase 3, Step 2: site identities and PostgreSQL validation

## Delivered

Sites now have permanent UUIDs and a versioned display name. Site memberships are
stored in a relational user/site table and govern authenticated request scope.
Equipment, documents and audit records have non-null site_id links; composite
foreign keys reject mismatched site ID/name pairs. Sensor, reading and work-order
scope continues through the linked equipment. Existing site names remain
compatible aliases for current request bodies and filters.

The legacy users.sites JSON field remains a compatibility mirror. Trusted ORM
membership updates synchronize the relational assignments atomically. Changing
that JSON directly with SQL does not grant access: request authorization loads
canonical memberships. This release has no public membership-administration API.

Workspace settings contains a Site directory. Users see only assigned sites.
Admin can edit display names with expected-version/CSRF checks; ID, canonical
alias, linked records and permissions remain unchanged. Display edits are audited.
This directory label does not rename legacy dropdown aliases.

## Upgrade your current SQLite installation

Stop Sentinel with Ctrl+C, run Apply-Phase3Step2.ps1, wait for
PHASE_3_STEP_2_INSTALLED, restart scripts/run.py and refresh with Ctrl+F5.
The installer validates hashes, backs up replaced files, validates the existing
schema and applies the checked SQLite updater. A pre-migration SQLite backup and
upgrade report are retained under data/backups and data/upgrade-reports.

The updater compares older schemas against immutable revisions before adopting
an unversioned database. It rejects schema drift and unexpected history. Revision
0003 backfills sites/memberships and site references without changing password
hashes, asset/sensor IDs, readings or document/audit contents. SQLite batch migration
uses a dedicated connection with FK checks suspended only during table recreation,
then checks foreign-key integrity before success. Failure restores the original
SQLite database; the installer restores previous application files.

scripts/upgrade_sensor_registry.py now forwards to scripts/upgrade_database.py.
Do not reapply an older update archive after this release. Automatic upgrades
remain SQLite-only; this installer does not edit .env or switch the live database.

## PostgreSQL verification actually performed

A separate temporary PostgreSQL 18.6 cluster was initialized on loopback. No
existing PostgreSQL service/database or the live SQLite data was used.

- Fresh migration through 0003 passed; Alembic metadata check found no changes.
- All 69 backend tests passed with a non-superuser application role holding DML
  privileges on the prepared test schema.
- A separate revision-0002 fixture upgraded while retaining password hashes,
  readings and stable sensor IDs; canonical memberships were backfilled.
- pg_dump custom-format backup and pg_restore into a separate empty database
  preserved those records, canonical asset/site links and revision 0003.
- The same 69-test suite passed on SQLite; TypeScript/production build passed.
- Site directory/admin display edits and phone form were reviewed through the UI.

This is functional compatibility and restore evidence, not production throughput,
HA, vendor integration or RPO/RTO certification. PostgreSQL row-level security and
remaining cross-record tenant constraints are not claimed. The existing Compose
example has not been exercised in this release; native Windows PostgreSQL 18.6
was the verified server. See evidence/phase3-step2-verification.json.

## Repeat PostgreSQL backend tests safely

Prepare a NEW local database named sentinel_test_<unique_suffix>, migrate it using
an owner role, and grant a separate non-superuser runtime role schema USAGE and
SELECT/INSERT/UPDATE/DELETE on the application tables plus sequence USAGE/SELECT.
The schema must be at revision 0003 and contain no users. Keep this separate from
your application database. Set SENTINEL_TEST_DATABASE_URL to its postgresql+psycopg
URL privately in your terminal, then run scripts/verify_postgres.py.

The verifier refuses non-loopback hosts, non-test database names, superuser runtime
roles, unprepared schemas or existing users. It writes a password-free result and
test log. Use a new prepared empty test database for another run. Never paste a
real connection password in chat or commit it to source control.

## Current status and next work

Step 2 is implemented and verified. Your live application remains SQLite until a
separate reviewed data-transfer/cutover step. Stable site IDs do not by themselves
complete enterprise multitenancy. Phase 3 remains PARTIAL.

Next: Step 3, normalized per-sensor events and validated unit handling. Durable
replay/quarantine and outage/capacity acceptance follow afterward.

The complete PowerShell installer was exercised against an isolated Step 1 source
copy. All existing user rows (including hashes), readings and sensor rows were
unchanged; two site identities and eleven canonical memberships were created.
