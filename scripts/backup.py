"""Consistent SQLite backup. No source data or credentials are packaged."""

import os
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
data = Path(os.getenv("SENTINEL_DATA_DIR", str(ROOT / "data")))
if os.getenv("DATABASE_URL", "sqlite").startswith("postgres"):
    raise SystemExit("Use pg_dump/PITR for PostgreSQL. See docs/OPERATIONS.md.")
source = data / "sentinel.db"
if not source.exists():
    raise SystemExit("No local database exists yet.")
output = ROOT / "data" / "backups"
output.mkdir(parents=True, exist_ok=True)
target = output / f'sentinel-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}.db'
with sqlite3.connect(source) as src, sqlite3.connect(target) as dest:
    src.backup(dest)
print(f"Created consistent SQLite backup: {target}")
print(
    "Restore only into a stopped, isolated application. Review and reconcile external effects first."
)
