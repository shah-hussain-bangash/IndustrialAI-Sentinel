# IndustrialAI Sentinel

A runnable local application for equipment condition monitoring, document evidence, independent maintenance review and work-order tracking. The React interface and FastAPI backend are connected; actions save to a real database.

**Featured case study:** [IndustrialAI Sentinel Case Study — equipment monitoring and controlled maintenance](docs/case-study/INDUSTRIALAI_SENTINEL_CASE_STUDY.md). Explore telemetry integrity, anomaly evaluation, independent review, work-order reconciliation, security, recovery and the current verification/release gaps.

**Start here:** this package includes both the complete source and a prebuilt `dist/` interface. No AI key, cloud account, MQTT broker or PostgreSQL server is needed for the default demonstration.

![Operations dashboard](docs/screenshots/overview.jpg)

## Open in Cursor

1. Extract the ZIP into a normal folder.
2. In Cursor choose **File → Open Folder** and select `industrialai-sentinel`.
3. Open this README and `docs/IMPLEMENTATION_STATUS.md`.
4. Open Cursor's terminal in the project root.
5. Run the quick start below. The optional `.code-workspace` and `.cursor/rules` files are included.

## Quick start using the included built interface

Install **Python 3.12**. On Windows:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe scripts/run.py
```

Open **http://127.0.0.1:8127**. The API and UI share this origin. Press Ctrl+C to stop. The first launch creates a SQLite database under `data/`, seeds synthetic equipment and creates demo accounts. Subsequent launches retain your changes.

On macOS or Linux:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python scripts/run.py
```

If port 8127 is already used, stop your own previous instance or set `PORT` and add that exact origin to `ALLOWED_ORIGINS` in `.env`. Do not terminate an unrelated application.

## Develop the interface and backend

Install **Node.js 24** and **pnpm 11.25.0** (`npm install -g pnpm@11.25.0`). In the root:

```powershell
pnpm install --frozen-lockfile
```

Terminal 1:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8127
```

Terminal 2:

```powershell
pnpm dev
```

Open **http://127.0.0.1:5187**. The frontend proxies `/api`, `/docs` and `/openapi.json` to the backend on 8127. This avoids cross-origin cookie configuration. After modifying the interface run `pnpm build` to update the prebuilt application served by `scripts/run.py`.

`start-windows.ps1` and `start-unix.sh` install dependencies, rebuild and launch when the required Python/Node/pnpm tools are present. The explicit terminal commands above are also available if script execution is restricted on your device. Never commit a real `.env` file.

## Try the complete maintenance workflow

1. Choose **Engineer** on the sign-in screen. Open Asset registry or Operations overview.
2. In Live monitoring generate a sample or run the five-second simulation. Choose rising vibration or recovery for P-101.
3. Select an asset and choose **Investigate equipment**, or use **New investigation**.
4. Inspect observed facts, possible explanations and cited procedures. Edit the recommendation if needed; this creates a new revision and invalidates approval.
5. Use the account menu to switch to **Approver**. Open the investigation, inspect source evidence, acknowledge review and approve the exact version. The author cannot approve their own version.
6. Switch to **Planner**. Open the approved investigation's Review & action tab and create a work order with an assignee and due date.
7. In Work orders dispatch it to the **local CMMS simulator**. Enable **Test uncertain response** to persist simulator acceptance without a confirmed reference.
8. Click **Reconcile existing order** to locate that accepted command without creating a duplicate.
9. Switch to **Technician** and record actual inspection findings to complete an in-progress order.
10. Open Activity & audit to review the saved decision history.

Newly registered assets receive their first synthetic snapshot when you use **Step once** in Live monitoring. For real data use the authenticated telemetry API.

Other functions: register assets, search/filter equipment, view sensor charts, acknowledge/review/resolve episodes, upload text-based PDFs or text files, search authorized knowledge, open source pages, export asset CSV, save display preferences and inspect runtime metrics.

## Demo accounts

All local demo accounts use **`SentinelDemo!2026`**, unless `DEMO_PASSWORD` is changed **before first seeding**. Quick account buttons authenticate through the backend; they do not bypass role checks.

| Account | Role |
|---|---|
| engineer@sentinel.local | Investigate, edit, monitor, upload and register |
| approver@sentinel.local | Independent approval or rejection |
| planner@sentinel.local | Plan, dispatch, reconcile and cancel |
| technician@sentinel.local | Record actual findings and completion |
| admin@sentinel.local | Local administration with self-approval still prohibited |
| restricted@sentinel.local | Read-only Habshan site observer; use manual sign-in |

Demo mode is for private development. Disabling it does not delete accounts already stored in a previously seeded database. Use a fresh database and follow `docs/OPERATIONS.md` before using non-demo data.

## Choose your own password

Sign in, open **Workspace settings → Change your password**, and enter your current
password, a new password (15–128 characters) and its confirmation. Your account
leaves the shared demo role list, and all its existing sessions are signed out.
Use email sign-in with the new password afterward. The email and role stay the
same. Changing `DEMO_PASSWORD` in `.env` does not reset existing accounts.

The password update requires authentication, CSRF and the current password. It
stores a salted password hash, records a password-free audit event and limits
attempts in the local server process. It does not provide forgotten-password
recovery, new-user registration or a shared multi-server rate limiter.

## Reliability Lab

Open **Reliability lab** for explainable fleet triage, shared-axis asset comparison,
scoped CSV briefs and saved what-if scenarios. See [the guide](docs/RELIABILITY_LAB.md)
for scoring, permissions, sample limits and model boundaries.

## Sensor registry (Phase 3, Step 1)

Open **Sensor registry** for stable channel identities, canonical units and versioned
freshness configuration. Existing-installation upgrade and backup instructions are
in [the step guide](docs/PHASE_3_STEP_1.md). Existing snapshot ingestion is preserved.

## Site identities and PostgreSQL verification (Phase 3, Step 2)

Open **Workspace settings → Site directory** for permanent site IDs and scoped
resource counts. PostgreSQL 18.6 migrations, non-superuser backend tests and a
backup/restore round trip were verified separately. The local installer preserves
SQLite; see [the step guide](docs/PHASE_3_STEP_2.md) before any database cutover.

## Verification

```powershell
pnpm build
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/evaluate_model.py
```

Tests cover authentication, CSRF, site isolation, roles, duplicate ingestion, idempotency conflicts, independent approval, stale versions, invalidation after edits, immutable draft history, uncertain dispatch reconciliation, controlled completion, document permission filtering, abstention and per-user preferences.

The model script reproduces synthetic training/holdout evaluation and exports an actual artifact and report to `data/model_artifacts`. Results are synthetic, not a validated industrial accuracy claim. Python and frontend dependency versions are pinned in `requirements.lock.txt` and `pnpm-lock.yaml`.

## Database and deployment

SQLite is the tested default. The SQLAlchemy models also support PostgreSQL via `DATABASE_URL`. Alembic revision `0001` is included and has been applied and checked on a fresh SQLite database. For a fresh managed database use `alembic upgrade head` and set `AUTO_CREATE_SCHEMA=false`.

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts/backup.py
```

`Dockerfile` builds the interface and serves the app as a non-root Python container. `compose.yaml` provides a local PostgreSQL-backed configuration bound to 127.0.0.1:8127. Docker/PostgreSQL runtime deployment must be verified in your environment; the reference test evidence uses SQLite. See `docs/OPERATIONS.md` for details.

## Implemented versus proposed

Read `docs/IMPLEMENTATION_STATUS.md`. This application completes a local maintenance workflow. The earlier master blueprint proposes additional enterprise capabilities; it does not mean they are already present here.

Implemented: sessions, role/site checks, ingestion, synthetic simulation, Isolation Forest evaluation, lexical/hashed-vector retrieval, source citations, PDF text extraction, versioned drafts, independent approval, persistent simulated CMMS reconciliation, work-order execution, audit, preferences, backup and tests.

Not claimed: live plant access, OEM procedures, real vendor CMMS integration, OIDC/SSO, OCR, semantic embedding models, hosted LLM orchestration, Kafka, TimescaleDB, pgvector, MLflow registry, LangGraph/MCP, calibrated digital twins, RUL estimation or production certification. These require further implementation, appropriate data, access and evaluation.

## Project map

```text
src/                 React screens, dialogs, charts and shared API client
backend/             FastAPI routes, domain rules, SQLAlchemy and analytics
migrations/          Initial Alembic revision and configuration
tests/               Backend workflow/security/integration tests
scripts/             Launch, model evaluation, SQLite backup, optional MQTT bridge
docs/                Operating instructions, architecture, status and test evidence
.cursor/rules/       Cursor project guidance
.github/workflows/   Build and test workflow
dist/                Included production frontend build
```

The OpenAPI document at **http://127.0.0.1:8127/openapi.json** is the authoritative implemented API. Interactive documentation is at **http://127.0.0.1:8127/docs**. Some route and data names differ from the earlier aspirational contract pack; use the generated implementation contract when developing this code.

## Latest increment: Phase 3, Step 3

Sensor registry now includes an event inspector, validated manual event entry and raw-to-canonical unit conversion. The batch API supports independent readings by sensor ID with duplicate/content checks and site authorization. Existing snapshot analytics stay separate. See [implementation contract](docs/PHASE_3_STEP_3.md).

## Latest increment: Phase 3, Step 4

Sensor event inspector now has an Equipment alignment tab. It checks four channels for freshness, good quality and a maximum 5-second observation spread, then explicitly publishes reviewed snapshots with source-event provenance. A manual four-channel test form is included. See [walkthrough and contract](docs/PHASE_3_STEP_4.md).

## Latest increment: Phase 3, Step 5

The inspector now includes Data review: bounded opt-in intake, rejected-payload evidence, authorized correction/replay and reasoned dismissal. Existing batch ingestion remains atomic and independent. See [walkthrough and API contract](docs/PHASE_3_STEP_5.md).

## Latest increment: Phase 3, Step 6

Data review now supports scoped search, all status filters, matching counts and keyset pagination with expiring account-bound navigation. Database revision stays 0006. See [walkthrough and API additions](docs/PHASE_3_STEP_6.md).

## Latest increment: Phase 3, Step 7

Workspace settings includes an all-site Admin backup/recovery check for SQLite. It verifies an isolated restoration without replacing the live database. Stored document text is included; original PDFs are not retained by the existing importer. See [walkthrough and recovery scope](docs/PHASE_3_STEP_7.md).

## Latest increment: Phase 3, Step 8

New PDF/TXT/MD uploads retain original bytes privately in the database. Original downloads check permissions and SHA-256; older documents explicitly show when originals were not retained. Recovery checks now verify archived file bytes and count legacy gaps. Schema revision is 0007. See [archive walkthrough and contract](docs/PHASE_3_STEP_8.md).


## Phase 3, Step 9 — scoped HTTP telemetry senders

Schema 0008 adds Admin-managed credentials restricted to one asset, expiry, rotation, revocation and auditable atomic event batches. Only credential hashes are stored; issuance secrets are displayed once and excluded from saved receipts. A hidden-prompt sample sender is included. Equipment snapshot publication remains an explicit reviewed action. 172 tests pass on SQLite and PostgreSQL 18.6; the frontend build passes. See [Step 9](docs/PHASE_3_STEP_9.md) for the API, walkthrough and boundaries. Browser acceptance remains pending.
