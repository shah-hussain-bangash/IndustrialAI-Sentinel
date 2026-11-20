import sqlite3
from test_sensor_upgrade import environment, legacy, run, snapshot


def test_step2_upgrade_preserves_all_existing_rows(tmp_path):
    env,path=environment(tmp_path);legacy(env);run(env,"-m","alembic","upgrade","0003")
    with sqlite3.connect(path) as db:
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'") if r[0]!="alembic_version"]
        before={t:db.execute(f'SELECT * FROM "{t}" ORDER BY 1').fetchall() for t in tables}
    run(env,"scripts/upgrade_database.py","--check-only")
    run(env,"scripts/upgrade_database.py")
    with sqlite3.connect(path) as db:
        for table,rows in before.items():assert db.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall()==rows
        assert db.execute("SELECT count(*) FROM sensor_events").fetchone()[0]==0
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0]=="0009"
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
    run(env,"-m","alembic","check")


def test_failed_event_upgrade_restores_step2(tmp_path):
    env,path=environment(tmp_path);legacy(env);run(env,"-m","alembic","upgrade","0003")
    before=snapshot(path)
    code="import runpy; import backend.sensors as s; s.ensure_sensors=lambda *a: (_ for _ in ()).throw(RuntimeError('forced failure')); runpy.run_path('scripts/upgrade_database.py',run_name='__main__')"
    result=run(env,"-c",code,ok=False)
    assert result.returncode!=0 and "original database restored" in result.stdout
    assert snapshot(path)==before
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0]=="0003"
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='sensor_events'").fetchone()
