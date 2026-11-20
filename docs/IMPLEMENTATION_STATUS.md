# Implementation status

This source package is a runnable local reference application, not a completed industrial production deployment. The UI invokes persistent backend operations. Synthetic equipment, procedures and CMMS responses are visibly labelled.

| Capability | Current behavior | Enterprise extension |
|---|---|---|
| Asset management | Persistent tagged assets, site scope, criticality, details and registration | Full hierarchy, sensor registry and effective-dated configuration |
| Sensor registry | Stable UUIDs, canonical units, versioned freshness and canonical equipment/site links | Independent events, conversions and reviewed 5-second alignment implemented; bounded quarantine, versioned correction/replay and dismissal implemented |
| Ingestion | Validated complete snapshots plus independent events with raw/canonical units, atomic batches and duplicate checks | Reviewed time-aligned projection implemented; quarantine and asset-scoped HTTP credentials implemented; broker/device attestation, edge spool and retention policy remain |
| Monitoring | Real stored trend queries, configured demo limit, condition index, episode transitions and simulation | Reviewed thresholds, sensor health, operating-state segmentation and calibrated risk |
| ML | Working Isolation Forest trained/evaluated with fixed independent synthetic seeds | Representative labelled industrial data, leakage review, uncertainty and domain acceptance |
| Knowledge | PDF text/text-file extraction, page references, scoped lexical and hashed-vector retrieval | OCR, reviewed applicability/version publication, semantic embeddings, full retrieval evaluation |
| Copilot | Extractive Q&A and deterministic evidence-based inspection drafts | Evaluated LLM integration; no external provider calls in this release |
| Workflow | Version checks, immutable draft revisions, independent approval, expiry, role checks | Durable distributed orchestration, granular permissions and approval policy integration |
| Work orders | Persistent local simulator, accepted-but-unknown response path, deduplicated reconciliation, completion and cancellation | Authorized vendor sandbox, external webhook verification and operational reconciliation |
| Identity | PBKDF2 passwords, opaque hashed sessions, HTTP-only cookie, CSRF and origin checks | Enterprise OIDC/SSO, managed identity and independent security review |
| Database | SQLite and isolated PostgreSQL 18.6 tests; migrations through 0008; canonical site memberships and composite site identity FKs | Live PostgreSQL cutover, additional tenant constraints, RLS and capacity testing |
| Operations | Health route, measured recent API p95, activity, backup utility and CI configuration | Metrics backend, traces, alerting, HA, load test and demonstrated restore objectives |
| Reliability Lab | Explainable triage, bounded shared-axis comparisons, constant-value checks, CSV briefs and auditable heuristic scenarios | Large-fleet optimization, representative-data evaluation and operational acceptance |
| Digital twin / RUL | Heuristic what-if comparison implemented; physical digital twin and RUL are not implemented or claimed | Calibrated physics/degradation model with suitable validation data |

## Important boundaries

- Condition index is an explicit heuristic derived from vibration/temperature, not a failure probability.
- Anomaly detector flags deviation from a synthetic distribution. It cannot establish a physical diagnosis.
- Seed procedures are authored demonstration text, not licensed or reviewed OEM instructions.
- Retrieval combines lexical overlap with deterministic hashed token vectors, not semantic model embeddings.
- No LLM is called. The engine and evidence limits are returned and shown in the UI.
- Work orders connect only to a persistent local simulator. Its uncertain-response case demonstrates application logic, not a distributed vendor guarantee.
- SQLite and isolated native PostgreSQL 18.6 functional tests passed. Docker deployment, production load and live cutover remain unverified.
- Document uploads are parsed synchronously and have size/page limits. Scanned files need OCR first; malware scanning and parser process isolation are future hardening work.
- Canonical membership filtering and composite site identity constraints are implemented. Full tenant row-level database policies and further cross-record constraints remain additional work.
- Session and rate limiting are local reference controls. Use reviewed enterprise identity and distributed controls before exposing this app.
- UI hiding/disabling actions is convenience; backend checks remain authoritative.

## Changes from the earlier planning pack

The earlier documents define a wider target. This implementation uses site names as scoped identifiers and a four-channel snapshot rather than the planned normalized per-sensor schema. The local API is generated from FastAPI and supersedes draft contracts for this code version. The exact-version recommendation workflow is implemented without claiming LangGraph/MCP or Celery orchestration. Keep plan and implementation documentation distinct when presenting the project.

## Recommended next development order

1. Replace demo identity with reviewed OIDC and implement membership administration.
2. Normalize site/asset/sensor identity, strengthen relational isolation and benchmark PostgreSQL.
3. Obtain appropriate industrial datasets/manuals and conduct ML/RAG evaluations with a domain reviewer.
4. Isolate document parsing, add reviewed OCR and publication/versioning controls.
5. Implement one authorized CMMS sandbox adapter with independent external reconciliation.
6. Add durable workers/outbox delivery, monitoring, restore and deployment verification.
7. Introduce an LLM or multi-agent workflow only after comparative quality/cost evaluation.

## Phase 3, Step 3

Independent sensor events, unit conversion and the event inspector are implemented. Snapshot-derived equipment analytics remain separate. See PHASE_3_STEP_3.md for the contract, demonstrated behavior and remaining work.

## Phase 3, Step 4

Reviewed, time-aligned independent sensor events can now be published as complete snapshots for the existing analytics. Source-event provenance, preview freshness checks and atomic publication are implemented. Only explicitly published frames affect snapshot analytics. See PHASE_3_STEP_4.md for the contract and remaining acceptance steps.

## Phase 3, Step 5

A bounded per-sensor quarantine queue now supports opt-in intake, immutable original rejection evidence, versioned terminal resolution, corrected-event lineage and audited dismissal. Existing batch API failures are not automatically captured. Durable broker ingestion, queue pagination, retention, live database cutover and operational validation remain pending. See PHASE_3_STEP_5.md.

## Phase 3, Step 6

The per-sensor review queue now has search, status counts and bidirectional keyset pagination beyond the previous latest-50 limit. Navigation checks current site access, binds filters/account and expires. Runtime is still a single-process local reference implementation; production retention, indexing/capacity, streaming integration and database cutover remain pending. See PHASE_3_STEP_6.md.

## Phase 3, Step 7

Checked SQLite backup and isolated read-only restoration verification are implemented, with all-site Admin controls, reports and a CLI. The scope is database records including extracted document text, not original uploaded files, application startup, off-device disaster recovery or PostgreSQL recovery management. Schema remains 0006. See PHASE_3_STEP_7.md.

## Phase 3, Step 8

Original-file retention for new uploads, scoped attachment downloads and original-byte recovery verification are implemented. Existing extracted-only documents remain unchanged with explicit original-unavailable labels. Revision is 0007. Original-file archival is now supported within the local database; production policy, object storage, capacity, parser isolation and retention remain pending. See PHASE_3_STEP_8.md.


## Phase 3, Step 9 — scoped HTTP telemetry senders

Schema 0008 adds Admin-managed credentials restricted to one asset, expiry, rotation, revocation and auditable atomic event batches. Only credential hashes are stored; issuance secrets are displayed once and excluded from saved receipts. A hidden-prompt sample sender is included. Equipment snapshot publication remains an explicit reviewed action. 172 tests pass on SQLite and PostgreSQL 18.6; the frontend build passes. See [Step 9](PHASE_3_STEP_9.md) for the API, walkthrough and boundaries. Browser acceptance remains pending.
