"""Run backend acceptance checks against an explicitly prepared, empty local test DB."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT=Path(__file__).resolve().parents[1]


def main():
    raw=os.getenv("SENTINEL_TEST_DATABASE_URL","")
    if not raw:raise SystemExit("Set SENTINEL_TEST_DATABASE_URL for a fresh, isolated local PostgreSQL test database.")
    url=make_url(raw)
    if url.drivername!="postgresql+psycopg" or url.host not in ("127.0.0.1","localhost") or not (url.database or "").startswith("sentinel_test_"):
        raise SystemExit("Refusing target: use a loopback postgresql+psycopg database named sentinel_test_*. No tests ran.")
    engine=create_engine(url)
    with engine.connect() as db:
        version=db.execute(text("SHOW server_version")).scalar_one()
        superuser=db.execute(text("SELECT rolsuper FROM pg_roles WHERE rolname=current_user")).scalar_one()
        revision=db.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        if superuser:raise SystemExit("Use a non-superuser runtime role with DML privileges on a prepared schema.")
        if revision!="0008":raise SystemExit("Prepare migration 0008 before running acceptance checks.")
        if db.execute(text("SELECT count(*) FROM users")).scalar_one():raise SystemExit("Test database must be fresh and empty. Existing users were found; nothing changed.")
    engine.dispose()
    output=Path(os.getenv("SENTINEL_PG_REPORT_DIR",str(ROOT/"data"/"verification"))).resolve()
    output.mkdir(parents=True,exist_ok=True)
    scratch=Path(tempfile.mkdtemp(prefix="postgres-pytest-",dir=output))
    result=subprocess.run([sys.executable,"-m","pytest","-q","-p","no:cacheprovider","--basetemp",str(scratch)],cwd=ROOT,env=os.environ.copy(),text=True,capture_output=True)
    log=result.stdout+result.stderr
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    (output/f"postgres-tests-{stamp}.txt").write_text(log,encoding="utf-8")
    count=re.search(r"(\d+) passed",log)
    report={"status":"passed" if result.returncode==0 else "failed","server_version":version,"schema_revision":revision,"runtime_superuser":bool(superuser),"passed_tests":int(count.group(1)) if count else None,"exit_code":result.returncode,"scope":"Isolated local PostgreSQL backend tests; not a live SQLite cutover or production load certification."}
    path=output/f"postgres-verification-{stamp}.json"
    path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report))
    print("VERIFICATION_REPORT="+str(path))
    if result.returncode:print(log[-4000:])
    raise SystemExit(result.returncode)


if __name__=="__main__":main()
