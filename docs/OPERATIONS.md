# Local operations and deployment

## Configuration

Copy `.env.example` to `.env` and set local values. `scripts/run.py` loads `.env`. For development use `uvicorn --env-file .env backend.main:app --reload --port 8127` when you need file-based configuration. `ALLOWED_ORIGINS` must include the exact browser origin. Secure cookies require HTTPS; keep `COOKIE_SECURE=false` only for local HTTP.

Demo users are inserted only into an empty database. `DEMO_MODE=false` stops quick-account discovery and simulation; it does not purge an already seeded database. For non-demo initialization use a fresh database and set a private `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD` before launch. There is no complete membership-administration UI or OIDC integration in this release.

## PostgreSQL and migrations

Set `DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE` using a private environment. For a new managed database:

```text
python -m alembic upgrade head
AUTO_CREATE_SCHEMA=false
python scripts/run.py
```

The first line is a command; the second denotes environment configuration, not a portable shell command. The application will seed only if the user table is empty and demo mode is enabled. Do not apply the initial migration blindly to a schema already created through `AUTO_CREATE_SCHEMA=true`; verify equivalence before stamping any revision. Review subsequent migration scripts and test rollback/restore on a staging copy.

## Docker

```text
docker compose up --build
```

Open 127.0.0.1:8127. The provided composition binds only loopback and starts a PostgreSQL service with a health check. It uses local demo credentials and is not a hardened production deployment. Set private credentials before any deployment outside a controlled local environment. Docker build and PostgreSQL runtime behavior need verification on your machine; SQLite is the tested default.

## Backup and restore

Run `python scripts/backup.py` for a consistent SQLite online backup. The backup contains user hashes, sessions, documents and application records; protect it. To verify restoration, stop a separate isolated test instance, place a copy under its own data directory and launch it against that directory. Validate counts, source records, draft revisions, approvals and work-order state. Reconcile external effects before enabling dispatch. Do not overwrite a working database during verification.

For PostgreSQL use the chosen service's backup/PITR process or an appropriate `pg_dump` procedure. Test storage, schema compatibility, artifact retention and access controls independently. No RPO/RTO has been demonstrated by the backup utility alone.

## Diagnostic checks

`/api/health` reports process/database mode. Authenticated `/api/operations` reports stored snapshots, service modes, current synthetic model metrics and p95 latency over the most recent in-memory API request sample. These are local diagnostics, not Prometheus/Grafana or an availability SLA.

If telemetry is stale, the condition becomes unknown after one hour. Confirm source connectivity and clock; do not infer health from silence. If an order is reconciling, do not repeat creation; use the reconciliation action. If a model result is surprising, check input units, quality, age and operating conditions before interpreting it as a fault.

## Optional MQTT bridge

Install `requirements-integrations.txt`. Set `MQTT_HOST`, `MQTT_PORT`, `MQTT_TLS`, optional broker credentials, `INGEST_EMAIL` and `INGEST_PASSWORD`. Run `python scripts/mqtt_bridge.py`. Publish the four-channel snapshot contract to `sentinel/<asset UUID>/snapshot`; the bridge adds the asset ID and calls the authenticated HTTP ingestion route.

The bridge is a connector example, not a durable edge spool. Publisher replay, gateway identity, dead-letter handling and offline buffering need implementation for a real deployment. Broker connection was not exercised in the default verification run.
