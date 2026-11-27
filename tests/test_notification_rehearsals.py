import uuid
import pytest
from sqlalchemy import select,func
from backend.database import (SessionLocal,NotificationRehearsal as Run,NotificationRehearsalEvent as Event,NotificationPlanRevision as Plan,
    NotificationPlanReview as Review,ConditionRule,ConditionRuleRevision,ConditionRuleMatch,User,AccountLink,Reading,WorkOrder,Audit,now)
from test_live_rules import cleanup_live_fixture
from test_notification_plans import clear_plans,match
from test_notification_reviews import proposal,command as review_command
from test_window_reviews import post


@pytest.fixture
def clock(monkeypatch):
    value=[now()];monkeypatch.setattr('backend.notification_rehearsals.now',lambda:value[0]);return value


def setup_run(client,sign_in):
    asset,rule,path,body=proposal(client,sign_in);sign_in('admin')
    assert post(client,path+'/reviews',review_command()).status_code==200
    mid=match(client,rule,asset)
    payload=dict(expected_plan_version=1,expected_rule_version=1,expected_review_version=1,match_id=mid,reason='Synthetic manual delivery rehearsal',confirmed=True)
    return asset,rule,path+'/rehearsals',payload,body


def control_body(action='simulate_success',version=1):
    return dict(action=action,expected_version=version,reason='Synthetic simulation outcome',confirmed=True)


def enqueue(client,path,payload):
    response=post(client,path,payload);assert response.status_code==200,response.text;return response.json()


def test_enqueue_deduplication_and_success_receipt(client,sign_in,clock):
    _,_,path,payload,_=setup_run(client,sign_in);key=str(uuid.uuid4())
    first=post(client,path,payload,key);assert first.status_code==200,first.text
    run=first.json();assert run['state']=='queued' and run['attempts']==0 and run['simulation_only'] and not run['delivery_enabled']
    assert post(client,path,payload,key).json()==run
    assert post(client,path,payload).status_code==409
    assert post(client,path,{**payload,'reason':'Changed'},key).status_code==409
    route=path+'/'+run['id']+'/control';attempt_key=str(uuid.uuid4())
    assert post(client,route,control_body('send_email')).status_code==422
    done=post(client,route,control_body(),attempt_key);assert done.status_code==200,done.text
    assert done.json()['state']=='simulated_success' and done.json()['attempts']==1
    assert post(client,route,control_body(),attempt_key).json()==done.json()
    assert post(client,route,control_body()).status_code==409
    assert [e['action'] for e in done.json()['history']]==['enqueue','simulate_success']


def test_retry_delays_early_retry_and_exhaustion(client,sign_in,clock):
    _,_,path,payload,_=setup_run(client,sign_in);run=enqueue(client,path,payload);route=path+'/'+run['id']+'/control'
    first=post(client,route,control_body('simulate_retryable_failure')).json()
    assert first['state']=='retry_wait' and first['next_attempt_at']==clock[0]+30
    assert post(client,route,control_body('simulate_retryable_failure',2)).status_code==409
    clock[0]+=30;second=post(client,route,control_body('simulate_retryable_failure',2)).json()
    assert second['next_attempt_at']==clock[0]+60 and second['attempts']==2
    clock[0]+=60;third=post(client,route,control_body('simulate_retryable_failure',3)).json()
    assert third['state']=='exhausted' and third['attempts']==3 and third['next_attempt_at'] is None
    assert len(third['history'])==4 and post(client,route,control_body(version=4)).status_code==409


@pytest.mark.parametrize('action,state,attempts',[('cancel','cancelled',0),('simulate_permanent_failure','simulated_failure',1)])
def test_terminal_outcomes(client,sign_in,clock,action,state,attempts):
    _,_,path,payload,_=setup_run(client,sign_in);run=enqueue(client,path,payload)
    result=post(client,path+'/'+run['id']+'/control',control_body(action));assert result.status_code==200,result.text
    assert result.json()['state']==state and result.json()['attempts']==attempts and result.json()['next_attempt_at'] is None


@pytest.mark.parametrize('change',['plan','review','recipient','rule'])
def test_changed_source_blocks_instead_of_attempting(client,sign_in,clock,change):
    _,rule,path,payload,plan_body=setup_run(client,sign_in);run=enqueue(client,path,payload);parent=path.removesuffix('/rehearsals')
    if change=='plan':assert post(client,parent,{**plan_body,'expected_version':1}).status_code==200
    elif change=='review':assert post(client,parent+'/reviews',{**review_command(review=1),'decision':'rejected'}).status_code==200
    elif change=='recipient':
        with SessionLocal() as db:person=db.get(User,plan_body['recipient_ids'][0]);old_role=person.role;person.role='disabled';db.commit()
    else:
        with SessionLocal() as db:
            old=db.get(ConditionRuleRevision,(rule['id'],1));db.add(ConditionRuleRevision(rule_id=rule['id'],version=2,name='New fixture head',settings=old.settings,actor_id=old.actor_id,actor_name=old.actor_name,reason='Synthetic rule head change'));db.get(ConditionRule,rule['id']).version=2;db.commit()
    try:
        # Read-side checks leave the queue untouched.
        view=client.get(path+'/'+run['id']).json();assert view['state']=='queued' and view['gate_reasons']
        result=post(client,path+'/'+run['id']+'/control',control_body());assert result.status_code==200,result.text
        assert result.json()['state']=='blocked' and result.json()['attempts']==0 and result.json()['history'][-1]['action']=='block'
        assert result.json()['history'][-1]['check_reasons']==view['gate_reasons']
        assert result.json()['history'][-1]['reason']==control_body()['reason']
    finally:
        if change=='recipient':
            with SessionLocal() as db:db.get(User,plan_body['recipient_ids'][0]).role=old_role;db.commit()


def test_cancellation_during_retry_wait_is_allowed_without_waiting(client,sign_in,clock):
    _,_,path,payload,_=setup_run(client,sign_in);run=enqueue(client,path,payload);route=path+'/'+run['id']+'/control'
    assert post(client,route,control_body('simulate_retryable_failure')).status_code==200
    result=post(client,route,control_body('cancel',2));assert result.json()['state']=='cancelled' and result.json()['attempts']==1


@pytest.mark.parametrize('changes',[{'confirmed':False},{'confirmed':1},{'reason':'bad'},{'expected_review_version':True},{'destination':'x@example.com'},{'force_send':True}])
def test_enqueue_validation(client,sign_in,clock,changes):
    _,_,path,payload,_=setup_run(client,sign_in)
    assert post(client,path,{**payload,**changes}).status_code==422
    assert client.get(path).json()['items']==[]


def test_requires_current_approval_and_own_exact_match(client,sign_in,clock):
    _,_,path,payload,_=setup_run(client,sign_in)
    assert post(client,path,{**payload,'expected_review_version':2}).status_code==409
    _,_,other,other_payload,_=setup_run(client,sign_in)
    assert post(client,path,{**payload,'match_id':other_payload['match_id']}).status_code==404
    parent=path.removesuffix('/rehearsals')
    assert post(client,parent+'/reviews',{**review_command(review=1),'decision':'rejected'}).status_code==200
    assert post(client,path,{**payload,'expected_review_version':2}).status_code==409


def test_access_scope_csrf_and_no_mail_or_operational_changes(client,sign_in,clock):
    _,_,path,payload,_=setup_run(client,sign_in)
    with SessionLocal() as db:before=[db.scalar(select(func.count()).select_from(m)) for m in (AccountLink,Reading,WorkOrder,ConditionRuleMatch)]
    client.headers.pop('X-CSRF-Token',None);assert post(client,path,payload).status_code==403
    sign_in('engineer');assert post(client,path,payload).status_code==403
    sign_in('admin');run=enqueue(client,path,payload)
    assert post(client,path+'/'+run['id']+'/control',control_body()).json()['state']=='simulated_success'
    with SessionLocal() as db:assert before==[db.scalar(select(func.count()).select_from(m)) for m in (AccountLink,Reading,WorkOrder,ConditionRuleMatch)]
    sign_in('engineer');assert client.get(path+'/'+run['id']).status_code==200
    assert post(client,path+'/'+run['id']+'/control',control_body()).status_code==403
    sign_in('admin')
    from backend.main import app
    from backend.security import current_user
    with SessionLocal() as db:
        scoped=db.scalar(select(User).where(User.email=='restricted@sentinel.local'));scoped.role='admin';app.dependency_overrides[current_user]=lambda:scoped
        try:
            assert client.get(path).status_code==404 and client.get(path+'/'+run['id']).status_code==404
            assert post(client,path+'/'+run['id']+'/control',control_body()).status_code==404
        finally:app.dependency_overrides.pop(current_user,None)
    client.cookies.clear();assert client.get(path).status_code==401


def test_stable_pagination_with_tied_creation_times_and_foreign_cursor(client,sign_in,clock):
    _,rule,path,payload,_=setup_run(client,sign_in);run=enqueue(client,path,payload)
    with SessionLocal() as db:
        original=db.get(Run,run['id']);source=db.get(ConditionRuleMatch,payload['match_id'])
        for _ in range(20):
            m=ConditionRuleMatch(rule_id=rule['id'],rule_version=1,state='paused',started_at=source.started_at,triggered_at=source.triggered_at,ended_at=source.triggered_at,trigger_reading_id=source.trigger_reading_id);db.add(m);db.flush()
            row=Run(rule_id=rule['id'],plan_version=1,review_version=1,match_id=m.id,recipients=original.recipients,version=1,state='queued',attempts=0,next_attempt_at=clock[0],actor_id=original.actor_id,actor_name=original.actor_name,reason='Synthetic pagination fixture',created=clock[0]);db.add(row);db.flush()
            db.add(Event(rehearsal_id=row.id,version=1,action='enqueue',attempt_number=0,actor_id=original.actor_id,actor_name=original.actor_name,reason='Synthetic history fixture',created=clock[0]))
        db.commit()
    first=client.get(path).json();last=client.get(path,params={'before_id':first['next_before_id']}).json()
    assert len(first['items'])==20 and len(last['items'])==1 and last['next_before_id'] is None
    assert len({r['id'] for r in first['items']+last['items']})==21
    _,_,other,other_payload,_=setup_run(client,sign_in);foreign=enqueue(client,other,other_payload)
    assert client.get(path,params={'before_id':foreign['id']}).status_code==404
