import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import socket

ROOT = Path(__file__).resolve().parents[1]


def environment(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    return {**os.environ,"SENTINEL_DATA_DIR":str(data),"DATABASE_URL":"sqlite:///"+(data/"sentinel.db").as_posix(),"PORT":"0","AUTO_CREATE_SCHEMA":"false","DEMO_MODE":"true"}, data/"sentinel.db"


def run(env,*args,ok=True):
    result=subprocess.run([sys.executable,*args],cwd=ROOT,env=env,text=True,capture_output=True,timeout=90)
    if ok: assert result.returncode==0,result.stdout+result.stderr
    return result


def legacy(env):
    run(env,"-m","alembic","upgrade","0001")
    code = "import sqlite3,json; from pathlib import Path; from backend.security import password_hash; p=Path(__import__('os').environ['SENTINEL_DATA_DIR'])/'sentinel.db'; db=sqlite3.connect(p); db.execute(\"INSERT INTO users VALUES (?,?,?,?,?,?)\",('legacy-user','legacy@sentinel.local','Legacy user','engineer',password_hash('Test-legacy-passphrase'),json.dumps(['Legacy site']))); db.execute(\"INSERT INTO assets VALUES (?,?,?,?,?,?,?,?,?,?,?)\",('legacy-asset','LEG-1','Legacy pump','Pump','Legacy site','Test','High','Fixture','2020-01-01',1,4.5)); db.execute(\"INSERT INTO readings VALUES (?,?,?,?,?,?,?,?,?)\",('legacy-reading','legacy-asset',1.0,2.0,70.0,5.0,100.0,'good','legacy-message')); db.commit()"
    run(env,"-c",code)


def snapshot(path):
    with sqlite3.connect(path) as db:
        return {"passwords":db.execute("SELECT id,password_hash FROM users ORDER BY id").fetchall(),"readings":db.execute("SELECT COUNT(*) FROM readings").fetchone()[0],"assets":db.execute("SELECT id FROM assets ORDER BY id").fetchall()}


def test_versioned_legacy_upgrade_preserves_data_backfills_and_repeats(tmp_path):
    env,path=environment(tmp_path);legacy(env)
    before=snapshot(path)
    first=run(env,"scripts/upgrade_sensor_registry.py")
    assert "DATABASE_BACKUP=" in first.stdout
    assert snapshot(path)==before
    with sqlite3.connect(path) as db:
        ids=db.execute("SELECT id FROM sensors ORDER BY id").fetchall()
        assert len(ids)==len(before["assets"])*4
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0]=="0009"
    run(env,"scripts/upgrade_sensor_registry.py")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT id FROM sensors ORDER BY id").fetchall()==ids
    run(env,"-m","alembic","check")


def test_unversioned_existing_installation_is_compared_before_adoption(tmp_path):
    env,path=environment(tmp_path);legacy(env)
    with sqlite3.connect(path) as db: db.execute("DROP TABLE alembic_version")
    before=snapshot(path)
    run(env,"scripts/upgrade_sensor_registry.py","--check-only")
    with sqlite3.connect(path) as db:
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='alembic_version'").fetchone()
    run(env,"scripts/upgrade_sensor_registry.py")
    assert snapshot(path)==before


def test_fresh_database_and_already_created_registry_are_supported(tmp_path):
    env,path=environment(tmp_path)
    run(env,"scripts/upgrade_sensor_registry.py")
    run(env,"-m","alembic","check")
    with sqlite3.connect(path) as db: db.execute("DROP TABLE alembic_version")
    run(env,"scripts/upgrade_sensor_registry.py")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0]=="0009"


def test_schema_drift_is_rejected_without_migration(tmp_path):
    env,path=environment(tmp_path);legacy(env)
    with sqlite3.connect(path) as db: db.execute("ALTER TABLE assets ADD COLUMN unexpected TEXT")
    before=snapshot(path)
    result=run(env,"scripts/upgrade_sensor_registry.py",ok=False)
    assert result.returncode!=0 and "schema differs" in result.stderr
    assert snapshot(path)==before
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0]=="0001"
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='sensors'").fetchone()


def test_failed_upgrade_restores_the_original_database(tmp_path):
    env,path=environment(tmp_path);legacy(env)
    before=snapshot(path)
    code="import runpy; import backend.sensors as s; s.ensure_sensors=lambda *a: (_ for _ in ()).throw(RuntimeError('forced test failure')); runpy.run_path('scripts/upgrade_sensor_registry.py',run_name='__main__')"
    result=run(env,"-c",code,ok=False)
    assert result.returncode!=0 and "original database restored" in result.stdout
    assert snapshot(path)==before
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0]=="0001"
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='sensors'").fetchone()


def test_upgrade_refuses_to_run_while_server_port_is_occupied(tmp_path):
    env,path=environment(tmp_path);legacy(env)
    before=snapshot(path)
    with socket.socket() as server:
        server.bind(("127.0.0.1",0));server.listen(1)
        env["PORT"]=str(server.getsockname()[1])
        result=run(env,"scripts/upgrade_sensor_registry.py",ok=False)
    assert result.returncode!=0 and "Stop the running Sentinel server" in result.stderr
    assert snapshot(path)==before
