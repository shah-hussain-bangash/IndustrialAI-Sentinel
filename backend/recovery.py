"""Checked SQLite snapshots and read-only restoration into a new isolated folder."""
import hashlib
import json
import shutil
import sqlite3
import threading
import time
import uuid
from contextlib import closing
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Audit, DATA, Site, User, engine, now
from .security import allow, current_user, get_db

MAX_BYTES = 256 * 1024 * 1024
TIME_BUDGET = 30
_RUN_LOCK = threading.Lock()
ROOT = DATA / "recovery"


class RecoveryError(ValueError):
    pass


def safe(path):
    path = Path(path)
    if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
        raise RecoveryError("Recovery paths must not be symbolic links or junctions.")
    return path


def sha256(path):
    digest = hashlib.sha256()
    with safe(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024*1024), b""): digest.update(chunk)
    return digest.hexdigest()


def read_db(path):
    # Immutable is appropriate only for the closed, complete backup/restore copies.
    return sqlite3.connect(safe(path).resolve().as_uri()+"?mode=ro&immutable=1", uri=True)


def quote(name):
    return '"'+name.replace('"','""')+'"'


def inventory(path):
    with closing(read_db(path)) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RecoveryError("Snapshot integrity check failed.")
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise RecoveryError("Snapshot foreign-key check failed.")
        schema = db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        records = {}
        for name in tables:
            columns = [row[1] for row in db.execute("PRAGMA table_info("+quote(name)+")")]
            query = "SELECT * FROM "+quote(name)+" ORDER BY "+", ".join(quote(c) for c in columns)
            content = hashlib.sha256(); count = 0
            for row in db.execute(query):
                values = [["bytes",v.hex()] if isinstance(v,bytes) else ["float",v.hex()] if isinstance(v,float) else [type(v).__name__,v] for v in row]
                encoded = json.dumps(values,ensure_ascii=True,separators=(",",":"),allow_nan=False).encode()
                content.update(len(encoded).to_bytes(8,"big"));content.update(encoded);count += 1
            records[name] = {"rows":count,"content_sha256":content.hexdigest()}
        revision = db.execute("SELECT version_num FROM alembic_version ORDER BY version_num").fetchall() if "alembic_version" in tables else []
        return {"schema_sha256":hashlib.sha256(json.dumps(schema,separators=(",",":")).encode()).hexdigest(), "revisions":[r[0] for r in revision], "tables":records}


def write_json(path, value):
    with safe(path).open("x",encoding="utf-8") as stream:
        json.dump(value,stream,indent=2,allow_nan=False)


def check_originals(path):
    with closing(read_db(path)) as db:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        documents=db.execute("SELECT count(*) FROM documents").fetchone()[0] if "documents" in tables else 0
        count=total=0
        if "document_originals" in tables:
            for content,size,checksum,document_checksum in db.execute("SELECT o.content,o.byte_size,o.checksum,d.checksum FROM document_originals o JOIN documents d ON d.id=o.document_id"):
                if not isinstance(content,bytes) or not 0<len(content)<=10485760 or len(content)!=size or hashlib.sha256(content).hexdigest()!=checksum or checksum!=document_checksum:
                    raise RecoveryError("An archived original failed its byte-size or checksum check.")
                count+=1;total+=size
        return {"archived":count,"bytes":total,"without_original":documents-count}


def create_backup(source, bundle):
    source = safe(Path(source)).resolve()
    if not source.is_file(): raise RecoveryError("The source SQLite database is unavailable.")
    if source.stat().st_size > MAX_BYTES: raise RecoveryError("Database exceeds the 256 MiB local recovery-check limit.")
    bundle = safe(bundle);bundle.mkdir(parents=False,exist_ok=False)
    target = bundle/"snapshot.db"
    started = time.monotonic()
    with closing(sqlite3.connect(source.as_uri()+"?mode=ro",uri=True,timeout=5)) as live, closing(sqlite3.connect(target)) as backup:
        page_size = live.execute("PRAGMA page_size").fetchone()[0]
        def progress(status, remaining, total):
            if total*page_size > MAX_BYTES: raise RecoveryError("Snapshot exceeds the local recovery-check size limit.")
            if time.monotonic()-started > TIME_BUDGET: raise RecoveryError("SQLite backup exceeded its 30-second copy budget.")
        live.backup(backup,pages=256,progress=progress,sleep=.01)
        backup.execute("PRAGMA journal_mode=DELETE")
        backup.commit()
    proof = inventory(target)
    originals=check_originals(target)
    manifest = {"format":1,"database_file":"snapshot.db","bytes":target.stat().st_size,"sha256":sha256(target),"inventory":proof,"originals":originals,"created":now(),"scope":"SQLite records, extracted document text and retained original file bytes; earlier documents may have no original. Environment configuration and external systems are not included."}
    write_json(bundle/"manifest.json",manifest)
    return manifest


def verify_restore(bundle, destination):
    bundle = safe(bundle)
    manifest_file = safe(bundle/"manifest.json")
    if not manifest_file.is_file() or manifest_file.stat().st_size > 1024*1024:
        raise RecoveryError("Backup manifest is missing or oversized.")
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (ValueError,UnicodeError): raise RecoveryError("Backup manifest is invalid.")
    if not isinstance(manifest,dict) or manifest.get("format") != 1 or manifest.get("database_file") != "snapshot.db":
        raise RecoveryError("Unsupported backup manifest or database path.")
    snapshot = safe(bundle/"snapshot.db")
    if not snapshot.is_file() or snapshot.stat().st_size > MAX_BYTES or snapshot.stat().st_size != manifest.get("bytes") or sha256(snapshot) != manifest.get("sha256"):
        raise RecoveryError("Backup checksum or size verification failed.")
    if inventory(snapshot) != manifest.get("inventory"):
        raise RecoveryError("Backup content does not match its inventory.")
    originals=check_originals(snapshot)
    if "originals" in manifest and originals!=manifest["originals"]:
        raise RecoveryError("Original-file inventory differs from the backup manifest.")
    destination = safe(destination)
    # Exclusive creation prevents overwriting either live data or a previous drill.
    destination.mkdir(parents=False,exist_ok=False)
    restored = destination/"snapshot.db"
    with snapshot.open("rb") as source, restored.open("xb") as target: shutil.copyfileobj(source,target,1024*1024)
    restored_inventory = inventory(restored)
    if sha256(restored) != manifest["sha256"] or restored_inventory != manifest["inventory"]:
        raise RecoveryError("Restored content differs from the checked backup.")
    if check_originals(restored)!=originals:
        raise RecoveryError("Restored original files differ from the backup.")
    return {"integrity":"ok","foreign_keys":"ok","checksum_match":True,"schema_match":True,"table_content_match":True,"table_counts":{name:proof["rows"] for name,proof in restored_inventory["tables"].items()},"revisions":restored_inventory["revisions"],"bytes":manifest["bytes"],"original_files_verified":originals["archived"],"original_file_bytes":originals["bytes"],"documents_without_original":originals["without_original"]}


def run_recovery(source, root, job_id):
    try:
        if str(uuid.UUID(job_id)) != job_id: raise ValueError("Noncanonical UUID")
    except (ValueError,TypeError): raise RecoveryError("Invalid recovery run identity.")
    root = safe(root);root.mkdir(parents=True,exist_ok=True)
    runs = safe(root/"runs");runs.mkdir(exist_ok=True)
    job = safe(runs/job_id)
    if job.exists():
        report = safe(job/"report.json")
        if report.is_file() and report.stat().st_size < 1024*1024:
            saved = json.loads(report.read_text(encoding="utf-8"))
            if isinstance(saved,dict) and saved.get("job_id")==job_id and saved.get("status") in ("passed","failed"):return saved
        raise RecoveryError("An incomplete recovery run already exists. Start a new check; partial artifacts are retained.")
    job.mkdir(exist_ok=False)
    started = now();timer = time.monotonic()
    result = {"job_id":job_id,"started":started,"scope":"Database-only isolated recovery verification; no live restore or application startup."}
    try:
        create_backup(source,job/"backup")
        result.update(verify_restore(job/"backup",job/"restored"),status="passed")
    except (RecoveryError,sqlite3.Error,OSError,ValueError):
        result.update(status="failed",reason="Recovery verification failed. Retained artifacts require local inspection; the live database was not restored.")
    result.update(finished=now(),duration_seconds=round(time.monotonic()-timer,3))
    write_json(job/"report.json",result)
    return result


def create_recovery_router(idempotent, finish):
    router = APIRouter(prefix="/api/recovery",tags=["Local recovery verification"])

    def administrator(db,user):
        allow(user,"admin")
        required = set(db.scalars(select(Site.id)))
        if not required or not required.issubset(set(getattr(user,"_site_ids",[]))):
            raise HTTPException(403,"Recovery checks require an administrator with access to every site.")

    @router.get("")
    def status(user:User=Depends(current_user),db:Session=Depends(get_db)):
        administrator(db,user)
        items=[]
        runs=safe(safe(ROOT)/"runs")
        if runs.exists():
            for folder in runs.iterdir():
                try:
                    uuid.UUID(folder.name);safe(folder)
                    path=safe(folder/"report.json")
                    if not path.is_file() or path.stat().st_size>1024*1024:continue
                    report=json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(report,dict) and report.get("job_id")==folder.name and report.get("status") in ("passed","failed") and isinstance(report.get("started"),(int,float)):items.append(report)
                except (ValueError,OSError):continue
        items.sort(key=lambda r:r.get("started",0),reverse=True)
        return {"supported":engine.dialect.name=="sqlite","items":items[:20],"schema_changes":False,"scope":"Stored SQLite records, extracted text and archived original file bytes. Earlier documents can lack originals. Configuration, dependencies and external systems are excluded.","storage":"data/recovery/runs","limits":"256 MiB database including original files; 30-second SQLite copy budget; no automatic cleanup or off-device copy."}

    class RunInput(BaseModel):
        model_config=ConfigDict(extra="forbid")

    @router.post("/verify")
    def verify(body:RunInput,request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
        administrator(db,user)
        if engine.dialect.name!="sqlite":raise HTTPException(409,"This local recovery check supports SQLite only. PostgreSQL needs a separately reviewed backup/restore procedure.")
        key,hashed,old=idempotent(db,request,user,body.model_dump())
        if old is not None:return old
        if not _RUN_LOCK.acquire(blocking=False):raise HTTPException(409,"Another recovery check is running. Wait for it to finish.")
        try:
            job_id=str(uuid.uuid5(uuid.NAMESPACE_URL,"industrialai-sentinel/recovery/"+key))
            result=run_recovery(Path(engine.url.database),ROOT,job_id)
            db.add(Audit(site=user.sites[0],actor=user.name,action="Isolated recovery check completed",target=job_id,details=f"Result {result['status']}; local SQLite backup and isolated read-only validation; no live restore."))
            return finish(db,key,hashed,result)
        except (RecoveryError,OSError,ValueError):
            db.rollback();raise HTTPException(409,"Recovery run could not complete. Inspect local recovery artifacts or start a new check.")
        finally:_RUN_LOCK.release()

    return router
