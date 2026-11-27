import uuid
import pytest
from sqlalchemy import select, func
from backend.database import (SessionLocal, MaintenanceWindowControl, MaintenanceWindowSuppression, MaintenanceWindowRevision,
    ConditionRuleMatch, ConditionRuleRevision, ConditionRuleDeployment, ConditionRuleReview, Reading, WorkOrder, now)
from test_live_rules import cleanup_live_fixture, draft, control, ingest
from test_maintenance_windows import clear_windows, body, create, equipment
from test_window_reviews import decision, post


@pytest.fixture
def clock(monkeypatch):
    clock=[int(now())]
    monkeypatch.setattr('backend.maintenance_controls.now',lambda:clock[0])
    monkeypatch.setattr('backend.live_rules.now',lambda:clock[0])
    return clock


def approved(client,sign_in,asset,clock,start=10,end=60):
    sign_in('engineer');data={**body(asset),'starts_at':clock[0]+start,'ends_at':clock[0]+end}
    saved=create(client,data);assert saved.status_code==201,saved.text
    path='/api/maintenance-windows/drafts/'+saved.json()['id']
    sign_in('admin');response=post(client,path+'/reviews',decision());assert response.status_code==200,response.text
    return path,data


def command(action='activate',version=0):
    return dict(action=action,expected_draft_version=1,expected_review_version=1,expected_control_version=version,
        reason='Synthetic controlled maintenance fixture',confirmed=True)


def test_activation_cancel_versions_freeze_and_idempotency(client,sign_in,clear_windows,clock):
    asset=equipment(client,sign_in);path,data=approved(client,sign_in,asset,clock)
    initial=client.get(path+'/control').json();assert initial['can_activate'] and initial['state']=='inactive'
    key=str(uuid.uuid4());response=post(client,path+'/control',command(),key);assert response.status_code==200,response.text
    assert response.json()['state']=='scheduled'
    assert post(client,path+'/control',command(),key).json()==response.json()
    assert post(client,path+'/control',command()).status_code==409
    assert post(client,path,{**data,'expected_version':1}).status_code==409
    assert post(client,path+'/reviews',decision(review_version=1)).status_code==409
    assert not client.get(path+'/reviews').json()['can_review']
    cancelled=post(client,path+'/control',command('cancel',1));assert cancelled.status_code==200,cancelled.text
    assert cancelled.json()['state']=='cancelled' and len(cancelled.json()['history'])==2
    assert post(client,path+'/control',command('cancel',2)).status_code==409
    assert post(client,path+'/control',command('activate',2)).status_code==409


def test_activation_requires_current_approval_and_future_interval(client,sign_in,clear_windows,clock):
    asset=equipment(client,sign_in);sign_in('engineer');saved=create(client,{**body(asset),'starts_at':clock[0]+10,'ends_at':clock[0]+60}).json()
    path='/api/maintenance-windows/drafts/'+saved['id'];sign_in('admin')
    assert post(client,path+'/control',command()).status_code==409
    assert post(client,path+'/reviews',{**decision(),'decision':'rejected'}).status_code==200
    assert post(client,path+'/control',command()).status_code==409
    assert post(client,path+'/reviews',decision(review_version=1)).status_code==200
    clock[0]+=10
    assert post(client,path+'/control',{**command(),'expected_review_version':2}).status_code==409


def test_overlap_and_adjacent_windows_and_equipment_isolation(client,sign_in,clear_windows,clock):
    asset=equipment(client,sign_in);path,_=approved(client,sign_in,asset,clock)
    assert post(client,path+'/control',command()).status_code==200
    overlap,_=approved(client,sign_in,asset,clock,start=20,end=70)
    assert post(client,overlap+'/control',command()).status_code==409
    adjacent,_=approved(client,sign_in,asset,clock,start=60,end=80)
    assert post(client,adjacent+'/control',command()).status_code==200
    other=next(row for row in client.get('/api/assets').json() if row['id']!=asset['id'])
    independent,_=approved(client,sign_in,other,clock)
    assert post(client,independent+'/control',command()).status_code==200


@pytest.mark.parametrize('changes',[{'confirmed':False},{'confirmed':1},{'reason':'bad'},{'expected_control_version':True},{'active':True},{'action':'delete'}])
def test_control_validation(client,sign_in,clear_windows,clock,changes):
    asset=equipment(client,sign_in);path,_=approved(client,sign_in,asset,clock)
    assert post(client,path+'/control',{**command(),**changes}).status_code==422
    assert client.get(path+'/control').json()['control_version']==0


def test_control_access_csrf_and_site_status(client,sign_in,clear_windows,clock):
    asset=equipment(client,sign_in);path,_=approved(client,sign_in,asset,clock)
    client.headers.pop('X-CSRF-Token',None);assert post(client,path+'/control',command()).status_code==403
    sign_in('engineer');assert post(client,path+'/control',command()).status_code==403
    sign_in('restricted');assert client.get(path+'/control').status_code==403
    assert client.get('/api/maintenance-windows/status',params={'asset_id':asset['id']}).status_code==404
    client.cookies.clear();assert client.get(path+'/control').status_code==401


def live_plan(client,sign_in,clock,persistence=0):
    asset,rule=draft(client,sign_in,persistence=persistence)
    with SessionLocal() as db:
        row=db.get(ConditionRuleRevision,(rule['id'],1));row.settings={**row.settings,'maximum_gap_seconds':300};db.commit()
    active=control(client,rule);assert active.status_code==200
    path,_=approved(client,sign_in,asset,clock)
    assert post(client,path+'/control',command()).status_code==200
    return asset,rule,path


def test_new_triggers_suppressed_readings_retained_and_expiry_resumes(client,sign_in,clear_windows,clock):
    base=clock[0];asset,rule,path=live_plan(client,sign_in,clock)
    clock[0]=base+10
    key=str(uuid.uuid4());message=str(uuid.uuid4())
    assert ingest(client,asset,base+10,7,key=key,message=message).status_code==200
    assert ingest(client,asset,base+10,7,key=key,message=message).status_code==200
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ConditionRuleMatch).where(ConditionRuleMatch.rule_id==rule['id']))==0
        assert db.scalar(select(func.count()).select_from(MaintenanceWindowSuppression))==1
        assert db.scalar(select(Reading).where(Reading.asset_id==asset['id'],Reading.timestamp==base+10)) is not None
        assert db.get(ConditionRuleDeployment,rule['id']).state=='active'
    status=client.get(path+'/control').json();assert status['state']=='suppressing' and status['suppressed_count']==1
    assert client.get('/api/maintenance-windows/status',params={'asset_id':asset['id']}).json()['items'][0]['state']=='suppressing'
    clock[0]=base+60;assert ingest(client,asset,base+60,7).status_code==200
    with SessionLocal() as db:assert db.scalar(select(ConditionRuleMatch).where(ConditionRuleMatch.rule_id==rule['id'])).state=='active'
    assert client.get(path+'/control').json()['state']=='expired'
    assert post(client,path+'/control',command('cancel',1)).status_code==409


def test_preexisting_match_not_hidden_or_resolved_and_normal_clearance(client,sign_in,clear_windows,clock):
    base=clock[0];asset,rule,path=live_plan(client,sign_in,clock)
    assert ingest(client,asset,base+1,7).status_code==200
    clock[0]=base+11;assert ingest(client,asset,base+11,7).status_code==200
    with SessionLocal() as db:
        row=db.scalar(select(ConditionRuleMatch).where(ConditionRuleMatch.rule_id==rule['id']));assert row.state=='active'
        assert db.scalar(select(func.count()).select_from(MaintenanceWindowSuppression))==0
        assert db.scalar(select(func.count()).select_from(ConditionRuleReview).where(ConditionRuleReview.match_id==row.id))==0
    clock[0]=base+12;assert ingest(client,asset,base+12,4).status_code==200
    with SessionLocal() as db:assert db.scalar(select(ConditionRuleMatch).where(ConditionRuleMatch.rule_id==rule['id'])).state=='cleared'


def test_no_reading_inside_window_resets_persistence(client,sign_in,clear_windows,clock):
    base=clock[0];asset,rule,path=live_plan(client,sign_in,clock,persistence=10)
    assert ingest(client,asset,base+1,7).status_code==200
    clock[0]=base+61;assert ingest(client,asset,base+61,7).status_code==200
    with SessionLocal() as db:assert not db.scalar(select(ConditionRuleMatch).where(ConditionRuleMatch.rule_id==rule['id']))
    clock[0]=base+71;assert ingest(client,asset,base+71,7).status_code==200
    with SessionLocal() as db:assert db.scalar(select(ConditionRuleMatch).where(ConditionRuleMatch.rule_id==rule['id'])).started_at==base+61


def test_cancel_ends_suppression_and_no_retrospective_suppression(client,sign_in,clear_windows,clock):
    base=clock[0];asset,rule,path=live_plan(client,sign_in,clock)
    clock[0]=base+11;assert ingest(client,asset,base+11,7).status_code==200
    clock[0]=base+12;assert post(client,path+'/control',command('cancel',1)).status_code==200
    clock[0]=base+13;assert ingest(client,asset,base+13,7).status_code==200
    with SessionLocal() as db:assert db.scalar(select(ConditionRuleMatch).where(ConditionRuleMatch.rule_id==rule['id'])).triggered_at==base+13


def test_delayed_reading_after_expiry_is_not_retrospectively_suppressed(client,sign_in,clear_windows,clock):
    base=clock[0];asset,rule,path=live_plan(client,sign_in,clock)
    clock[0]=base+70;assert ingest(client,asset,base+20,7).status_code==200
    with SessionLocal() as db:
        assert db.scalar(select(ConditionRuleMatch).where(ConditionRuleMatch.rule_id==rule['id'])) is not None
        assert db.scalar(select(func.count()).select_from(MaintenanceWindowSuppression))==0


def test_cancel_before_start_does_not_reset_candidate(client,sign_in,clear_windows,clock):
    base=clock[0];asset,rule,path=live_plan(client,sign_in,clock,persistence=10)
    assert ingest(client,asset,base+1,7).status_code==200
    assert post(client,path+'/control',command('cancel',1)).status_code==200
    clock[0]=base+11;assert ingest(client,asset,base+11,7).status_code==200
    with SessionLocal() as db:assert db.scalar(select(ConditionRuleMatch).where(ConditionRuleMatch.rule_id==rule['id'])).started_at==base+1


def test_quality_and_other_equipment_remain_independent(client,sign_in,clear_windows,clock):
    base=clock[0];asset,rule,path=live_plan(client,sign_in,clock)
    other,other_rule=draft(client,sign_in,persistence=0);assert control(client,other_rule).status_code==200
    clock[0]=base+11
    assert ingest(client,asset,base+11,7,quality='bad').status_code==200
    assert ingest(client,other,base+11,7).status_code==200
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(MaintenanceWindowSuppression))==0
        assert not db.scalar(select(ConditionRuleMatch).where(ConditionRuleMatch.rule_id==rule['id']))
        assert db.scalar(select(ConditionRuleMatch).where(ConditionRuleMatch.rule_id==other_rule['id'])).state=='active'


def test_cancellation_restarts_persistence_and_evidence_has_exact_references(client,sign_in,clear_windows,clock):
    base=clock[0];asset,rule,path=live_plan(client,sign_in,clock,persistence=10)
    assert ingest(client,asset,base+1,7).status_code==200
    clock[0]=base+11;assert ingest(client,asset,base+11,7).status_code==200
    clock[0]=base+12;assert post(client,path+'/control',command('cancel',1)).status_code==200
    clock[0]=base+13;assert ingest(client,asset,base+13,7).status_code==200
    with SessionLocal() as db:
        assert not db.scalar(select(ConditionRuleMatch).where(ConditionRuleMatch.rule_id==rule['id']))
        evidence=db.scalar(select(MaintenanceWindowSuppression))
        assert evidence.rule_id==rule['id'] and evidence.rule_version==1 and evidence.draft_id==path.split('/')[-1] and evidence.control_version==1
        assert db.get(Reading,evidence.reading_id).asset_id==asset['id']
    clock[0]=base+23;assert ingest(client,asset,base+23,7).status_code==200
    with SessionLocal() as db:assert db.scalar(select(ConditionRuleMatch).where(ConditionRuleMatch.rule_id==rule['id'])).started_at==base+13
