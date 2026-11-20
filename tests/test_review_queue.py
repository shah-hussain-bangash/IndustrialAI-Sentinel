import uuid

import pytest
from sqlalchemy import select

from backend.database import Sensor, SensorQuarantine, SessionLocal, User, now
from backend.seed import SITES
from test_projections import equipment
from test_quarantine import sensor_id, resolve


@pytest.fixture
def large_queue(client,equipment):
    id=sensor_id(client,equipment)
    clock=now()-60
    with SessionLocal() as db:
        actor=db.scalar(select(User.id).where(User.email=="engineer@sentinel.local"))
        rows=[SensorQuarantine(sensor_id=id,payload_hash=uuid.uuid4().hex*2,raw_payload={"message_id":f"QUEUE-{i:03}","source":"search-fixture","raw_value":212,"raw_unit":"invalid-test"},validation_errors=["Unsupported temperature unit"],submitted_by=actor,created=clock) for i in range(63)]
        db.add_all(rows);db.commit();expected=sorted((r.id for r in rows),reverse=True)
    return id,expected


def get_page(client,id,**params):
    return client.get("/api/sensor-quarantine",params={"sensor_id":id,**params})


def test_browses_beyond_50_without_duplicate_or_missing_equal_time_rows(client,large_queue):
    id,expected=large_queue;seen=[];cursor=None
    while True:
        r=get_page(client,id,limit=10,**({"cursor":cursor} if cursor else {}));assert r.status_code==200,r.text
        body=r.json();seen.extend(row["id"] for row in body["items"])
        assert body["total_matching"]==63 and body["summary"]=={"pending":63,"replayed":0,"dismissed":0}
        cursor=body["next_cursor"]
        if not cursor:break
    assert seen==expected and len(set(seen))==63


def test_first_page_token_supports_previous_and_fixed_new_submission_boundary(client,large_queue):
    id,expected=large_queue;first=get_page(client,id,limit=10).json()
    with SessionLocal() as db:
        actor=db.scalar(select(User.id).where(User.email=="engineer@sentinel.local"))
        new=SensorQuarantine(sensor_id=id,payload_hash=uuid.uuid4().hex*2,raw_payload={"source":"new-arrival"},validation_errors=["Missing fields"],submitted_by=actor)
        db.add(new);db.commit();new_id=new.id
    second=get_page(client,id,limit=10,cursor=first["next_cursor"]).json()
    back=get_page(client,id,limit=10,cursor=first["page_cursor"]).json()
    assert [r["id"] for r in second["items"]]==expected[10:20]
    assert [r["id"] for r in back["items"]]==expected[:10] and back["total_matching"]==63
    refreshed=get_page(client,id,limit=10).json()
    assert refreshed["items"][0]["id"]==new_id and refreshed["total_matching"]==64


@pytest.mark.parametrize("field,value",[("status","all"),("q","changed-search"),("limit",25)])
def test_cursors_are_bound_to_filters_and_page_size(client,large_queue,field,value):
    id,_=large_queue;cursor=get_page(client,id,limit=10).json()["next_cursor"]
    params={"limit":10,"cursor":cursor,field:value}
    assert get_page(client,id,**params).status_code==422


def test_invalid_tampered_expired_and_restarted_cursors_fail_cleanly(client,large_queue,monkeypatch):
    import backend.review_queue as module
    id,_=large_queue;first=get_page(client,id,limit=10).json();cursor=first["next_cursor"]
    for token in ("broken",cursor+"x","x"*2049):
        assert get_page(client,id,limit=10,cursor=token).status_code==422
    with monkeypatch.context() as patch:
        patch.setattr(module,"now",lambda:first["cursor_expires_at"]+1)
        assert get_page(client,id,limit=10,cursor=cursor).status_code==422
    with monkeypatch.context() as patch:
        patch.setattr(module,"_CURSOR_SECRET",b"replacement-process-test-key")
        assert get_page(client,id,limit=10,cursor=cursor).status_code==422
    assert get_page(client,id,limit=10).status_code==200


def test_cursor_requires_same_user_and_sensor_and_current_site_access(client,large_queue,equipment,sign_in):
    id,_=large_queue;cursor=get_page(client,id,limit=10).json()["next_cursor"]
    other=next(s["id"] for s in client.get("/api/sensors",params={"asset_id":equipment}).json()["items"] if s["id"]!=id)
    assert get_page(client,other,limit=10,cursor=cursor).status_code==422
    sign_in("technician")
    assert get_page(client,id,limit=10,cursor=cursor).status_code==422
    assert get_page(client,id).status_code==200
    sign_in()
    with SessionLocal() as db:
        u=db.scalar(select(User).where(User.email=="engineer@sentinel.local"));sites=u.sites;uid=u.id;u.sites=[SITES[1]];db.commit()
    try:assert get_page(client,id,limit=10,cursor=cursor).status_code==404
    finally:
        with SessionLocal() as db:db.get(User,uid).sites=sites;db.commit()


def test_search_matches_original_corrected_reason_and_ids_with_status_counts(client,large_queue):
    id,_=large_queue;one=get_page(client,id,q="queue-062",status="all").json()
    assert one["total_matching"]==1
    item=one["items"][0]
    assert get_page(client,id,q=item["id"]).json()["total_matching"]==1
    with SessionLocal() as db:
        row=db.get(SensorQuarantine,item["id"])
        # Exercise real dismissal, including its persistent reason.
        assert row.status=="pending"
    result=resolve(client,item,"dismiss",reason="Verified ALPHA-special recovery case.");assert result.status_code==200
    filtered=get_page(client,id,q="alpha-SPECIAL",status="all").json()
    assert filtered["summary"]=={"pending":0,"replayed":0,"dismissed":1} and filtered["total_matching"]==1
    assert get_page(client,id,q="alpha-special",status="pending").json()["total_matching"]==0
    assert get_page(client,id,status="dismissed").json()["total_matching"]==1
    assert get_page(client,id,q="search-FIXTURE",status="all").json()["total_matching"]==63


def test_search_wildcards_are_literal_and_limits_apply(client,large_queue):
    id,_=large_queue
    for query in ("%","raw_unit_","' OR 1=1 --","no-such-submission"):
        result=get_page(client,id,q=query).json();assert result["total_matching"]==0 and not result["items"]
    assert get_page(client,id,q="x"*101).status_code==422
    assert get_page(client,id,limit=101).status_code==422
    assert get_page(client,id,q="  QUEUE-062  ").json()["total_matching"]==1


def test_status_changes_are_live_without_repeating_page_keys(client,large_queue):
    id,expected=large_queue;first=get_page(client,id,limit=10).json()
    assert resolve(client,first["items"][0],"dismiss").status_code==200
    second=get_page(client,id,limit=10,cursor=first["next_cursor"]).json()
    assert second["total_matching"]==62 and second["summary"]["dismissed"]==1
    assert [r["id"] for r in second["items"]]==expected[10:20]


def test_queue_metrics_and_search_do_not_leak_other_sensor_rows(client,large_queue,equipment):
    id,_=large_queue
    with SessionLocal() as db:
        other=db.scalar(select(Sensor).where(Sensor.asset_id==equipment,Sensor.id!=id))
        actor=db.scalar(select(User.id).where(User.email=="engineer@sentinel.local"))
        db.add(SensorQuarantine(sensor_id=other.id,payload_hash=uuid.uuid4().hex*2,raw_payload={"source":"exclusive-neighbor"},validation_errors=["Invalid"],submitted_by=actor));db.commit()
    assert get_page(client,id,q="exclusive-neighbor",status="all").json()["total_matching"]==0
    assert get_page(client,id,status="all").json()["summary"]["pending"]==63
