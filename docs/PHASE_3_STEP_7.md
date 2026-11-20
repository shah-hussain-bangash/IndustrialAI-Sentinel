# Phase 3, Step 7: local backup and isolated recovery verification

This increment adds an all-site administrator recovery panel and a command-line check for the current local SQLite runtime. It creates a checked database backup, copies that backup into a new isolated folder, and reads the restored database to compare schema, integrity, foreign keys and every table's contents. It never replaces the live database or launches an application against the restored copy. Schema stays 0006; no dependency install is required.

## Install and walkthrough

Prerequisite: Phase 3 Step 6 installed. Stop Sentinel with Ctrl+C, run Apply-Phase3Step7.ps1 against the existing project, restart scripts/run.py and refresh Ctrl+F5. The updater backs up code and SQLite and checks the existing schema; no data migration is added.

1. Sign in as Admin. The account must have canonical access to every site because a database snapshot contains all sites and authentication records.
2. Open Workspace settings and locate Backup & recovery verification.
3. Click Run recovery check once. The interface stays busy while it creates a local backup and validates an isolated restoration.
4. Confirm Recovery verification passed. Expand the latest check to inspect checksum/schema/content matches and the restored row counts, including documents, sensor events, review decisions and snapshot provenance.
5. Click Refresh checks or reopen settings to confirm the report remains listed. The live application continues using its original database.

Engineer and other non-admin accounts see an explanation but cannot invoke or inspect the database-wide check. Partial-site Admin accounts are rejected by the server. The request requires the current authenticated session, CSRF and Idempotency-Key.

## Stored document scope

The current importer stores extracted PDF/text passages, metadata and a source checksum in the documents table. It does not retain original uploaded file bytes. The recovery check covers those stored passages and metadata, not original PDF files. Original-file archival must be implemented separately; this increment does not fabricate or recover missing originals. Configuration/.env, dependencies, model artifacts and external systems are also outside the database-only backup.

## Command-line alternative

From the project folder run:

.\.venv\Scripts\python.exe scripts/verify_recovery.py

The utility loads the project .env without overriding existing environment values, uses the configured SQLite database and prints a metadata-only report plus its absolute location. Exit code is 0 on pass and 1 on a recorded verification failure. PostgreSQL is refused. It does not accept a caller-supplied restore target or overwrite the live database. The older scripts/backup.py remains a separate simple snapshot utility.

## Evidence and storage

Default run folder: data/recovery/runs/<run UUID> (under SENTINEL_DATA_DIR if configured).

- backup/snapshot.db: consistent SQLite online backup including committed WAL data.
- backup/manifest.json: SHA256, byte size, migration history, schema hash and per-table row counts/content hashes.
- restored/snapshot.db: newly created isolated restoration, never used as the live database.
- report.json: metadata-only result, duration, verification flags and row counts. It contains no raw passwords, document passages or sensor values.

The check compares the restored file checksum with the checked backup, runs SQLite integrity_check and foreign_key_check, and recomputes deterministic schema/table inventories. Bytes, floating-point values, nulls and row ordering are handled explicitly. Changing a backup without updating its manifest fails verification. Checksums detect inconsistency; a manifest stored beside its backup is not an independent signature or off-site trust anchor.

Database snapshots contain authentication/session records and stored content. They stay on local disk and are excluded from source packages. No backup-download or live-restore endpoint is added. Actual operational recovery requires a stopped, isolated application, session/credential handling and external-effect reconciliation under a separately reviewed procedure.

## Limits and failure behavior

The local database limit is 256 MiB. A 30-second budget applies to the SQLite copy operation; content verification can take additional time. Durations are measured local checks, not promised RPO/RTO or disaster-recovery certification. A process-local lock prevents overlapping API checks in the current single-process runtime. Multiworker coordination, scheduling, retention, encryption and off-device copies remain further work.

API retries use a deterministic run UUID derived from the scoped idempotency key. A finished report can be reused without making another backup; completion is audited and its response persisted. Failed runs and partial artifacts are retained. If a run is incomplete, inspect the local artifacts, then use Refresh checks before starting a new run. Existing restoration directories are never reused or overwritten. Managed symbolic links/junctions and unsupported manifest paths are rejected.

GET /api/recovery returns engine support, the latest 20 reports and scope/limits. POST /api/recovery/verify accepts only an empty object. Only an Admin with all-site canonical memberships may use either endpoint; authorization is checked before replaying a completed response. PostgreSQL reports unsupported and POST returns 409. The new control does not automatically manage PostgreSQL backups.

## Verification

151 tests passed on SQLite. The same full 151-test suite passed with the application on isolated PostgreSQL 18.6 using a non-superuser role; that run verifies the unsupported PostgreSQL path while recovery-copy unit tests still use isolated SQLite fixtures. Tests cover complete content recovery, committed WAL content, unchanged source files, corruption, broken foreign keys, inconsistent/traversing manifests, existing destinations, size/copy-budget failures, idempotency, concurrent-run rejection, admin/site/CSRF checks and caller-path rejection. Existing application workflows also pass.

TypeScript and Vite production build passed. Existing migration/metadata and PostgreSQL logical dump/restore checks passed. Interactive browser verification remains pending because local browser access was disabled. The installed-app walkthrough above is the acceptance check. One existing Starlette test-client deprecation warning remains.

Phase 3 is still partial: original-file archival, operational backup policy, retention/partitioning, broker/device integration, production capacity, live PostgreSQL cutover and full recovery objectives remain outstanding.
