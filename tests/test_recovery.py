import json
import sqlite3
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from backend import recovery
from backend.database import Audit, SessionLocal, User, engine
from backend.seed import SITES


@pytest.fixture
def source(tmp_path):
    path=tmp_path/"source.db"
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("CREATE TABLE users(id INTEGER PRIMARY KEY,password_hash TEXT)")
        db.execute("CREATE TABLE documents(id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id), text TEXT)")
        db.execute("CREATE TABLE samples(id INTEGER PRIMARY KEY, value REAL, original BLOB)")
        db.execute("CREATE TABLE alembic_version(version_num TEXT)")
        db.execute("INSERT INTO alembic_version VALUES ('0006')")
        db.execute("INSERT INTO users VALUES (1,'sensitive-fixture-value-never-in-report')")
        db.execute("INSERT INTO documents VALUES (1,1,'Extracted procedure text preserved through recovery.')")
        db.executemany("INSERT INTO samples VALUES (?,?,?)",[(i,i*.25,bytes([i])) for i in range(20)])
    return path


def test_full_recovery_preserves_source_and_checks_every_table(source,tmp_path):
    before=recovery.sha256(source);root=tmp_path/"recovery";job=str(uuid.uuid4())
    report=recovery.run_recovery(source,root,job)
    assert report["status"]=="passed",report
    assert report["integrity"]==report["foreign_keys"]=="ok"
    assert report["checksum_match"] and report["schema_match"] and report["table_content_match"]
    assert report["table_counts"]=={"alembic_version":1,"documents":1,"samples":20,"users":1}
    assert report["revisions"]==["0006"]
    assert recovery.sha256(source)==before
    restored=root/"runs"/job/"restored/snapshot.db"
    assert recovery.inventory(restored)==recovery.inventory(source)
    assert "sensitive-fixture-value-never-in-report" not in json.dumps(report)
    assert "Extracted procedure text" not in json.dumps(report)
    original_report=(root/"runs"/job/"report.json").read_bytes()
    assert recovery.run_recovery(source,root,job)==report
    assert (root/"runs"/job/"report.json").read_bytes()==original_report


def test_checksum_detects_changed_backup_before_restoration(source,tmp_path):
    bundle=tmp_path/"backup";recovery.create_backup(source,bundle)
    with sqlite3.connect(bundle/"snapshot.db") as db:db.execute("UPDATE samples SET value=999 WHERE id=1")
    destination=tmp_path/"restored"
    with pytest.raises(recovery.RecoveryError,match="checksum"):recovery.verify_restore(bundle,destination)
    assert not destination.exists()


@pytest.mark.parametrize("change",["traversal","inventory","size","list","format"])
def test_untrusted_or_inconsistent_manifest_cannot_direct_restoration(source,tmp_path,change):
    bundle=tmp_path/"backup";recovery.create_backup(source,bundle)
    p=bundle/"manifest.json";manifest=json.loads(p.read_text(encoding="utf-8"))
    if change=="traversal":manifest["database_file"]="../source.db"
    if change=="inventory":manifest["inventory"]["tables"]["users"]["rows"]=999
    if change=="size":manifest["bytes"]+=1
    if change=="list":manifest=[]
    if change=="format":manifest["format"]=99
    p.write_text(json.dumps(manifest),encoding="utf-8")
    destination=tmp_path/"restored"
    with pytest.raises(recovery.RecoveryError):recovery.verify_restore(bundle,destination)
    assert not destination.exists()


def test_existing_destination_and_invalid_run_ids_never_overwrite_live_data(source,tmp_path):
    before=recovery.sha256(source);bundle=tmp_path/"backup";recovery.create_backup(source,bundle)
    with pytest.raises(FileExistsError):recovery.verify_restore(bundle,source.parent)
    assert recovery.sha256(source)==before
    for id in ("../outside","not-a-run",uuid.uuid4().hex):
        with pytest.raises(recovery.RecoveryError):recovery.run_recovery(source,tmp_path/"recovery",id)
    incomplete=tmp_path/"recovery/runs"/str(uuid.uuid4());incomplete.mkdir(parents=True)
    with pytest.raises(recovery.RecoveryError,match="incomplete"):recovery.run_recovery(source,tmp_path/"recovery",incomplete.name)
    assert recovery.sha256(source)==before


def test_failure_is_reported_without_replacing_source(source,tmp_path,monkeypatch):
    before=recovery.sha256(source)
    monkeypatch.setattr(recovery,"MAX_BYTES",1)
    report=recovery.run_recovery(source,tmp_path/"recovery",str(uuid.uuid4()))
    assert report["status"]=="failed" and "live database was not restored" in report["reason"]
    assert recovery.sha256(source)==before


def test_broken_foreign_keys_fail_verification(source,tmp_path):
    with sqlite3.connect(source) as db:db.execute("UPDATE documents SET user_id=999")
    before=recovery.sha256(source)
    report=recovery.run_recovery(source,tmp_path/"recovery",str(uuid.uuid4()))
    assert report["status"]=="failed" and recovery.sha256(source)==before


def test_copy_time_budget_and_corruption_fail_closed(source,tmp_path,monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(recovery,"TIME_BUDGET",-1)
        report=recovery.run_recovery(source,tmp_path/"recovery",str(uuid.uuid4()))
        assert report["status"]=="failed"
    damaged=tmp_path/"bad.db";damaged.write_bytes(b"not a SQLite database")
    assert recovery.run_recovery(damaged,tmp_path/"recovery",str(uuid.uuid4()))["status"]=="failed"


def test_reads_committed_wal_data(source,tmp_path):
    # Keep WAL open so the committed update is not yet merged into the main file.
    live=sqlite3.connect(source)
    try:
        live.execute("PRAGMA journal_mode=WAL")
        live.execute("UPDATE documents SET text='Latest committed WAL text' WHERE id=1");live.commit()
        root=tmp_path/"recovery";job=str(uuid.uuid4())
        assert recovery.run_recovery(source,root,job)["status"]=="passed"
        restored=sqlite3.connect(root/"runs"/job/"restored/snapshot.db")
        try:assert restored.execute("SELECT text FROM documents").fetchone()[0]=="Latest committed WAL text"
        finally:restored.close()
    finally:live.close()


def verify(client,key=None,**body):
    return client.post("/api/recovery/verify",json=body,headers={"Idempotency-Key":key or str(uuid.uuid4())})


def test_admin_route_idempotency_evidence_and_supported_engine(client,sign_in):
    assert client.get("/api/recovery").status_code==401
    sign_in("admin");status=client.get("/api/recovery");assert status.status_code==200
    if engine.dialect.name!="sqlite":
        assert status.json()["supported"] is False
        assert verify(client).status_code==409
        return
    key=str(uuid.uuid4());result=verify(client,key);assert result.status_code==200,result.text
    report=result.json();assert report["status"]=="passed"
    assert "sensor_events" in report["table_counts"] and "sensor_quarantine" in report["table_counts"]
    assert verify(client,key).json()==report
    items=client.get("/api/recovery").json()["items"]
    assert sum(r["job_id"]==report["job_id"] for r in items)==1
    with SessionLocal() as db:
        records=list(db.scalars(select(Audit).where(Audit.action=="Isolated recovery check completed",Audit.target==report["job_id"])))
        assert len(records)==1


def test_recovery_requires_admin_all_sites_and_csrf(client,sign_in):
    sign_in()
    assert client.get("/api/recovery").status_code==403 and verify(client).status_code==403
    sign_in("admin");client.headers.pop("X-CSRF-Token")
    assert verify(client).status_code==403
    sign_in("admin")
    with SessionLocal() as db:
        u=db.scalar(select(User).where(User.email=="admin@sentinel.local"));sites=u.sites;uid=u.id;u.sites=[SITES[1]];db.commit()
    try:
        assert client.get("/api/recovery").status_code==403
        assert verify(client).status_code==403
    finally:
        with SessionLocal() as db:db.get(User,uid).sites=sites;db.commit()


def test_recovery_rejects_caller_paths_and_concurrent_checks(client,sign_in):
    sign_in("admin")
    assert verify(client,destination="C:/industrialai-sentinel/data").status_code==422
    assert verify(client,source="arbitrary").status_code==422
    if engine.dialect.name!="sqlite":return
    assert recovery._RUN_LOCK.acquire(blocking=False)
    try:assert verify(client).status_code==409
    finally:recovery._RUN_LOCK.release()
