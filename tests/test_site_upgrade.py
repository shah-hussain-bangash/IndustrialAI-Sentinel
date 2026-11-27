import json
import sqlite3
import uuid

from test_sensor_upgrade import environment, legacy, run, snapshot


def test_step1_to_site_ids_preserves_records_and_permissions(tmp_path):
    env,path=environment(tmp_path)
    legacy(env);run(env,"-m","alembic","upgrade","0002")
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?)",("legacy-doc","Legacy manual","manual.txt","Legacy site","Pump","1.0",json.dumps(["Old source text"]),"0"*64,1.0))
        db.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?,?)",("legacy-audit","Legacy site","Legacy user","Fixture","legacy-asset","Preserved evidence",1.0))
        sensors=db.execute("SELECT id FROM sensors ORDER BY id").fetchall()
    before=snapshot(path)
    result=run(env,"scripts/upgrade_database.py")
    assert "MAINTENANCE_WINDOW_DRAFT_UPGRADE=PASS" in result.stdout
    assert snapshot(path)==before
    expected=str(uuid.uuid5(uuid.NAMESPACE_URL,"industrialai-sentinel/site/Legacy site"))
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT id,name FROM sites").fetchone()==(expected,"Legacy site")
        assert db.execute("SELECT user_id,site_id FROM site_memberships").fetchone()==("legacy-user",expected)
        for table in ("assets","documents","audit_events"):
            assert db.execute(f"SELECT site_id FROM {table}").fetchone()[0]==expected
        assert db.execute("SELECT id FROM sensors ORDER BY id").fetchall()==sensors
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
        assert db.execute("SELECT details FROM audit_events").fetchone()[0]=="Preserved evidence"
    run(env,"scripts/upgrade_database.py")
    run(env,"-m","alembic","check")


def test_invalid_legacy_membership_restores_original_step1_database(tmp_path):
    env,path=environment(tmp_path)
    legacy(env);run(env,"-m","alembic","upgrade","0002")
    with sqlite3.connect(path) as db:db.execute("UPDATE users SET sites=?",(json.dumps({"invalid":"membership"}),))
    before=snapshot(path)
    result=run(env,"scripts/upgrade_database.py",ok=False)
    assert result.returncode!=0 and "original database restored" in result.stdout
    assert snapshot(path)==before
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0]=="0002"
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='sites'").fetchone()
