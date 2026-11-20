"""Create a local SQLite backup and verify an isolated restoration; never restore live."""
import json
import os
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));os.chdir(ROOT)
from dotenv import load_dotenv
load_dotenv(ROOT/".env",override=False)
from backend.database import DATA,engine
from backend.recovery import run_recovery

if engine.dialect.name!="sqlite":raise SystemExit("This verification utility supports SQLite only. PostgreSQL requires a separate recovery procedure.")
report=run_recovery(Path(engine.url.database),DATA/"recovery",str(uuid.uuid4()))
print(json.dumps(report,indent=2))
print("RECOVERY_REPORT="+str(DATA/"recovery"/"runs"/report["job_id"]/"report.json"))
engine.dispose()
raise SystemExit(0 if report["status"]=="passed" else 1)
