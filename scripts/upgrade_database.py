"""Checked, backed-up SQLite upgrade to the current application schema."""

import argparse
import json
import os
import socket
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=False)


def upgrade():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    # A stopped application prevents legacy startup/create_all from racing migration.
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", int(os.getenv("PORT", "8127"))))
        except OSError:
            raise SystemExit("Stop the running Sentinel server with Ctrl+C before applying the database upgrade.")

    from sqlalchemy import MetaData, inspect
    from alembic import command
    from alembic.config import Config
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from backend.database import Base, DATABASE_URL, engine, SessionLocal, Asset, Sensor
    from backend.sensors import ensure_sensors
    from backend.schema_history import historical_metadata
    from sqlalchemy import select

    if engine.dialect.name != "sqlite":
        raise SystemExit("This automatic upgrade supports SQLite only. PostgreSQL needs a separately reviewed migration run.")
    source = Path(engine.url.database).resolve()
    tables = set(inspect(engine).get_table_names())
    revision = None
    with engine.connect() as conn:
        if "alembic_version" in tables:
            versions = conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalars().all()
            if len(versions) > 1 or versions and versions[0] not in ("0001", "0002", "0003", "0004", "0005", "0006", "0007", "0008", "0009", "0010", "0011", "0012", "0013", "0014", "0015", "0016", "0017", "0018", "0019", "0020", "0021"):
                raise SystemExit("Unexpected migration history. No changes made; review this database separately.")
            revision = versions[0] if versions else None
        inferred = "0021" if "notification_plan_reviews" in tables else "0020" if "notification_plan_revisions" in tables else "0019" if "maintenance_window_controls" in tables else "0018" if "maintenance_window_reviews" in tables else "0017" if "maintenance_window_drafts" in tables else "0016" if "condition_match_investigations" in tables else "0015" if "condition_rule_assignments" in tables else "0014" if "condition_rule_reviews" in tables else "0013" if "condition_rule_deployments" in tables else "0012" if "condition_rules" in tables else "0011" if "mfa_credentials" in tables else "0010" if "account_links" in tables else "0009" if "organization" in tables else "0008" if "telemetry_gateways" in tables else "0007" if "document_originals" in tables else "0006" if "sensor_quarantine" in tables else "0005" if "snapshot_projections" in tables else "0004" if "sensor_events" in tables else "0003" if "sites" in tables else "0002" if "sensors" in tables else "0001"
        if tables - {"alembic_version"}:
            target = Base.metadata if inferred == "0021" else historical_metadata(inferred)
            diffs = compare_metadata(MigrationContext.configure(conn, opts={"compare_type":True}), target)
            if diffs:
                raise SystemExit("The existing schema differs from the expected application schema. Nothing was stamped or migrated; review the database first.")
            if conn.exec_driver_sql("PRAGMA foreign_key_check").fetchone():
                raise SystemExit("Existing foreign-key integrity failed. Nothing changed.")
        elif revision:
            raise SystemExit("Migration history exists without application tables. Nothing changed.")
    if revision and int(revision) > int(inferred):
        raise SystemExit("Migration history is ahead of its actual tables. Review the database before proceeding.")
    if args.check_only:
        print("UPGRADE_PREFLIGHT=PASS; schema and server-stop checks passed")
        engine.dispose()
        return

    backup = None
    if source.exists():
        backup_dir = source.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / ("before-notification-plan-reviews-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".db")
        with sqlite3.connect(source) as src, sqlite3.connect(backup) as dest:
            if src.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise SystemExit("Database integrity check failed. Upgrade stopped.")
            src.backup(dest)
            if dest.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise SystemExit("Backup integrity check failed. Upgrade stopped.")
        print("DATABASE_BACKUP=" + str(backup))
    try:
        config = Config(str(ROOT / "alembic.ini"))
        if tables - {"alembic_version"} and revision != inferred:
            command.stamp(config, inferred)
        command.upgrade(config, "head")
        with SessionLocal() as db:
            assets = list(db.scalars(select(Asset)))
            ensure_sensors(db, assets)
            db.commit()
            count = len(list(db.scalars(select(Sensor.id))))
        report = {"revision":"0021", "database":str(source), "backup":str(backup) if backup else None, "assets":len(assets), "sensors":count, "existing_readings_and_passwords":"preserved"}
        report_dir = source.parent / "upgrade-reports"
        report_dir.mkdir(parents=True,exist_ok=True)
        report_file = report_dir / ("notification-plan-reviews-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
        report_file.write_text(json.dumps(report,indent=2),encoding="utf-8")
        engine.dispose()
        print(f"NOTIFICATION_PLAN_REVIEW_UPGRADE=PASS; revision=0021; sensors={count}")
        print("UPGRADE_REPORT=" + str(report_file))
    except Exception:
        engine.dispose()
        if backup:
            with sqlite3.connect(backup) as src, sqlite3.connect(source) as dest:
                src.backup(dest)
            print("UPGRADE_FAILED; original database restored from " + str(backup))
        raise



if __name__ == "__main__":
    upgrade()
