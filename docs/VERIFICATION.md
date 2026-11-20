# Verification record

Verified on 30 October 2026 in a Windows Python 3.12 environment.

| Check | Result |
|---|---|
| Install Python locked requirements in a fresh virtual environment | Passed |
| Dependency consistency with pip check | Passed |
| TypeScript check and Vite production build | Passed |
| Backend security, workflow and static-serving tests | 24 passed |
| Initial Alembic migration on a fresh SQLite database | Applied successfully |
| Compare migrated schema to model metadata | No new upgrade operations detected |
| Synthetic Isolation Forest evaluation | Report and artifact generated |
| SQLite online backup | Created and inspected with integrity_check = ok |

## Browser checks

Inspected desktop overview, asset registry, monitoring controls, knowledge retrieval, investigation evidence, work-order board, audit timeline and workspace settings. Generated a sensor snapshot through the interface. Queried procedure evidence through the interface after security-token recovery. Opened a page-two citation at page two and closed the nested source dialog independently. Checked a 390-pixel mobile viewport and confirmed no horizontal overflow. The dashboard screenshot is retained under `docs/screenshots`.

## Test coverage

Tests exercise anonymous access rejection, session logout, invalid passwords, CSRF, foreign origins, cross-site restrictions, asset creation, role restrictions, duplicate ingestion, message identity conflicts, finite/timestamp validation, independent review, wrong-role approval, revised authorship and immutable history, stale-version rejection, approval invalidation, blocked unapproved orders, uncertain simulator outcome reconciliation, completion requirements, document upload and scoped retrieval, unsupported uploads, abstention, per-account preferences, model/CSV responses, bad-quality handling, new-asset demo initialization and built-interface/API documentation delivery.

## Verification limits

The runtime tests use SQLite and synthetic data. Docker images, PostgreSQL runtime deployment, the optional MQTT bridge against a broker, real vendor systems, plant interfaces, industrial prediction accuracy and enterprise identity were not verified in this run. Backup integrity inspection is not an end-to-end disaster-recovery drill or proof of an RPO/RTO. A Starlette warning notes future test-client migration from httpx; it did not fail the tests.

The source pack intentionally excludes runtime databases, sessions, `.env`, installed dependencies and caches. Fresh demo data is generated at first launch.


## Reliability Lab release

47 backend tests passed, plus TypeScript and production build. See RELIABILITY_LAB.md for the tested cases, UI checks and remaining limits. Preview saves used the source copy's synthetic data; the installed application database was not used.


## Phase 3, Step 1

59 tests passed, including six registry and six migration/recovery cases. TypeScript and production build passed. SQLite legacy and versioned upgrade paths were verified on isolated databases. See PHASE_3_STEP_1.md.


## Phase 3, Step 2

69 backend tests passed on SQLite and PostgreSQL 18.6. The PostgreSQL suite used a non-superuser runtime role. Fresh/legacy migrations, metadata comparison and pg_dump/restore preservation passed. TypeScript/build and site directory UI checks passed. See PHASE_3_STEP_2.md and evidence/phase3-step2-verification.json for scope; no live application cutover was performed.

## Phase 3, Step 3 — 31 October 2026

91 backend tests passed on SQLite and 91 on isolated PostgreSQL 18.6 with non-superuser runtime privileges, schema revision 0004. Fresh/legacy migrations, metadata comparisons, SQLite backup restoration on failure, and PostgreSQL logical dump/restore including a sensor event passed. TypeScript/build and desktop/390px browser checks passed. This supersedes prior verification counts for the current release; production load, broker integration and live cutover remain unverified. See PHASE_3_STEP_3.md.

The full PowerShell updater was exercised on a populated copy of the previous revision 0003 release. All rows in users, readings, sensors, assets, sites, memberships, documents and audit events remained identical; revision became 0004, the new event table was empty and foreign-key checks passed. Installed payload hashes matched the manifest.

## Phase 3, Step 4 — 2 November 2026

107 tests passed on SQLite and 107 on isolated PostgreSQL 18.6 using a non-superuser runtime role; schema revision 0005. Fresh/legacy migrations, metadata checks, SQLite upgrade preservation and failure restoration passed. PostgreSQL dump/restore preserved real tested projection rows and their source events/readings. TypeScript/Vite build passed. Interactive UI verification is pending because local browser access was disabled; follow PHASE_3_STEP_4.md after installation. This supersedes previous counts for the current release.

The full PowerShell updater was exercised on a populated copy of the previous revision 0004 release. All rows in users, readings, sensors, assets, sites, memberships, documents, audit events and independent events remained identical; revision became 0005, the new projection table was empty and foreign-key checks passed. Installed payload hashes matched the manifest.

## Phase 3, Step 5 — 2 November 2026

125 tests passed on SQLite and 125 on isolated PostgreSQL 18.6 using a non-superuser runtime role; revision 0006. Existing workflows and new bounded intake, evidence preservation, correction/replay, dismissal, status/role/site controls and rollback checks passed. Fresh/legacy migrations and metadata comparison passed. Logical dump/restore preserved actual tested quarantine, events, readings and snapshot provenance. TypeScript/Vite build passed. Interactive browser acceptance remains pending because local browser access was disabled. See PHASE_3_STEP_5.md.

The full Step 5 PowerShell updater passed on a populated previous-release copy. Every existing application table matched its checked pre-upgrade backup, including accounts, readings, independent events and a published snapshot provenance record. Revision became 0006, the new quarantine table was empty, foreign-key checks passed and installed payload hashes matched the manifest.

## Phase 3, Step 6 — 2 November 2026

136 tests passed on SQLite and 136 on isolated PostgreSQL 18.6 with a non-superuser application role. Revision remains 0006. Search, literal patterns, counters, 63-row equal-time pagination, boundary refresh, token expiry/tampering/filter/account checks and live status changes passed. TypeScript/Vite build, metadata and logical restore checks passed. Interactive browser acceptance is pending because local browser access was disabled. See PHASE_3_STEP_6.md.

The full Step 6 PowerShell updater passed on a populated previous-release copy. Every existing application table matched its checked pre-upgrade backup, including accounts, readings, independent events and a published snapshot provenance record. Revision stayed 0006 and all three previous pending/replayed/dismissed items were preserved, foreign-key checks passed and installed payload hashes matched the manifest.

## Phase 3, Step 7 — 3 November 2026

151 tests passed on SQLite and 151 in the isolated PostgreSQL 18.6 application run. The new recovery action is SQLite-only; PostgreSQL tests verify refusal and use separate SQLite unit fixtures for copy/restore behavior. Committed WAL recovery, every-table comparison, unchanged source, corruption/manifest/destination limits, access controls and idempotency passed. TypeScript/build and existing migration/logical-restore checks passed. Browser acceptance is pending. See PHASE_3_STEP_7.md.

The full Step 7 PowerShell updater passed on a populated previous-release copy. Every existing application table matched its checked pre-upgrade backup, including accounts, readings, independent events and a published snapshot provenance record. Revision stayed 0006 and all three previous pending/replayed/dismissed items were preserved, foreign-key checks passed and installed payload hashes matched the manifest.

The new verify_recovery.py CLI was executed successfully against the upgraded previous-release fixture. It recovered all 20 tables, including 6 stored documents, 1441 snapshots, 5 independent events, 3 review items and 1 projection record. Checksum/schema/content comparisons and foreign-key/integrity checks passed; original database rows remained identical to the installer backup. These are isolated fixture measurements, not production recovery guarantees.

## Phase 3, Step 8 — 3 November 2026

163 tests passed on SQLite and 163 on isolated PostgreSQL 18.6 under a non-superuser application role; revision 0007. Exact PDF/TXT/MD archival/download, deferred metadata, scoped authorization, safe filenames, idempotency, rollback, corruption detection, legacy gaps, original recovery and old manifests passed. PostgreSQL dump/restore preserved tested original binary rows. TypeScript/build and metadata/migration checks passed. Browser acceptance remains pending. See PHASE_3_STEP_8.md.

The full Step 8 PowerShell updater passed on a populated previous-release copy. Every existing application table matched its checked pre-upgrade backup, including accounts, readings, independent events and a published snapshot provenance record. Revision became 0007 and all three previous pending/replayed/dismissed items were preserved, foreign-key checks passed and installed payload hashes matched the manifest.

The upgraded prior-release fixture passed an actual API upload/download/recovery workflow: the text original returned byte-for-byte, a successful recovery verified 1 archived original and explicitly counted 6 legacy records without originals, and pre-upgrade recovery report files remained unchanged. This is isolated acceptance evidence; the installed browser walkthrough remains pending.


## Phase 3, Step 9 — scoped HTTP telemetry senders

Schema 0008 adds Admin-managed credentials restricted to one asset, expiry, rotation, revocation and auditable atomic event batches. Only credential hashes are stored; issuance secrets are displayed once and excluded from saved receipts. A hidden-prompt sample sender is included. Equipment snapshot publication remains an explicit reviewed action. 172 tests pass on SQLite and PostgreSQL 18.6; the frontend build passes. See [Step 9](PHASE_3_STEP_9.md) for the API, walkthrough and boundaries. Browser acceptance remains pending.

The full Step 9 PowerShell updater passed on a populated previous-release copy. Every existing application table matched its checked pre-upgrade backup, including accounts, readings, independent events and a published snapshot provenance record. Revision became 0008 and all three previous pending/replayed/dismissed items were preserved, foreign-key checks passed and installed payload hashes matched the manifest.

The Step 9 bundled sender passed against a separate local HTTP server using an upgraded populated fixture. It submitted four events, rejected the previous credential after rotation, accepted the new credential, then rejected it after revocation. No equipment snapshot was published and plaintext credentials were absent from persisted receipts and audit details. No user application or live equipment was used.
