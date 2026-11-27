import uuid
import pytest
from sqlalchemy import select,delete,func
from backend.database import (SessionLocal,NotificationPlanRevision as Plan,NotificationPlanReview,User,SiteMembership,Audit,Reading,AccountLink,
    ConditionRuleMatch,ConditionRuleRevision,ConditionRuleDeployment,ConditionRuleReview,WorkOrder)
from test_live_rules import cleanup_live_fixture,draft,control,ingest
from test_window_reviews import post


@pytest.fixture(autouse=True)
def clear_plans(cleanup_live_fixture):
    yield
    with SessionLocal() as db:db.execute(delete(NotificationPlanReview));db.execute(delete(Plan));db.commit()


def setup_plan(client,sign_in):
    asset,rule=draft(client,sign_in,persistence=0)
    path='/api/notification-plans/rules/'+rule['id'];info=client.get(path).json()
    person=next(p for p in info['recipients'] if p['role']=='engineer')
    body=dict(expected_version=0,expected_rule_version=1,name='Synthetic notification plan',recipient_ids=[person['id']],reason='Synthetic inactive planning fixture')
    return asset,rule,path,body


def match(client,rule,asset):
    active=control(client,rule);assert active.status_code==200
    assert ingest(client,asset,active.json()['activated_at']+1,7).status_code==200
    with SessionLocal() as db:return db.scalar(select(ConditionRuleMatch.id).where(ConditionRuleMatch.rule_id==rule['id']))


def test_plan_save_revisions_idempotency_and_audit(client,sign_in):
    asset,rule,path,body=setup_plan(client,sign_in);key=str(uuid.uuid4())
    first=post(client,path,body,key);assert first.status_code==200,first.text
    assert first.json()['active'] is False and first.json()['version']==1
    assert post(client,path,body,key).json()==first.json()
    assert post(client,path,{**body,'name':'Different'},key).status_code==409
    assert post(client,path,body).status_code==409
    assert post(client,path,{**body,'expected_version':1,'name':'Revised plan'}).json()['version']==2
    history=client.get(path+'/history').json()['items']
    assert [r['version'] for r in history]==[2,1] and history[1]['name']==body['name']
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Audit).where(Audit.action=='Notification plan draft saved',Audit.details.contains(rule['id'])))==2


@pytest.mark.parametrize('changes',[{'recipient_ids':[]},{'recipient_ids':['missing']},{'recipient_ids':['a','a']},{'recipient_ids':['x'*37]},
    {'expected_version':True},{'name':' '},{'reason':'bad'},{'name':'bad\nname'},{'active':True},{'destination':'person@example.com'},{'recipient_ids':[str(i) for i in range(11)]}])
def test_plan_validation(client,sign_in,changes):
    _,_,path,body=setup_plan(client,sign_in)
    assert post(client,path,{**body,**changes}).status_code==422
    assert client.get(path).json()['current'] is None


def test_preview_is_readonly_historical_and_never_exposes_addresses(client,sign_in):
    asset,rule,path,body=setup_plan(client,sign_in);mid=match(client,rule,asset)
    assert post(client,path,body).status_code==200
    with SessionLocal() as db:
        before={m.__tablename__:db.scalar(select(func.count()).select_from(m)) for m in (Plan,Audit,Reading,AccountLink,ConditionRuleMatch,ConditionRuleDeployment,ConditionRuleReview,WorkOrder)}
    answer=post(client,path+'/preview',{'expected_plan_version':1,'match_id':mid});assert answer.status_code==200,answer.text
    result=answer.json();assert result['preview_only'] and not result['delivery_enabled'] and not result['queued']
    assert result['match_id']==mid and result['match_route']=='#conditions/'+mid and result['plan']['rule_version']==1
    assert result['recipients'][0]['currently_eligible'] and not result['recipients'][0]['email_address_configured']
    assert result['eligible_configured_count']==0 and '@sentinel.local' not in answer.text
    assert 'email' not in client.get(path).json()['recipients'][0]
    with SessionLocal() as db:
        assert before=={m.__tablename__:db.scalar(select(func.count()).select_from(m)) for m in (Plan,Audit,Reading,AccountLink,ConditionRuleMatch,ConditionRuleDeployment,ConditionRuleReview,WorkOrder)}


def test_recipient_revocation_is_rechecked_and_history_retained(client,sign_in):
    asset,rule,path,body=setup_plan(client,sign_in);mid=match(client,rule,asset)
    assert post(client,path,body).status_code==200
    with SessionLocal() as db:
        person=db.get(User,body['recipient_ids'][0]);old_role=person.role;person.role='disabled';db.commit()
    try:
        response=post(client,path+'/preview',{'expected_plan_version':1,'match_id':mid});assert response.status_code==200,response.text
        assert response.json()['recipients'][0]['currently_eligible'] is False
        assert post(client,path,{**body,'expected_version':1}).status_code==422
        assert client.get(path+'/history').json()['items'][0]['recipients'][0]['id']==body['recipient_ids'][0]
        assert body['recipient_ids'][0] not in [p['id'] for p in client.get(path).json()['recipients']]
    finally:
        with SessionLocal() as db:db.get(User,body['recipient_ids'][0]).role=old_role;db.commit()


def test_site_role_csrf_and_missing_match_guards(client,sign_in):
    asset,rule,path,body=setup_plan(client,sign_in)
    client.headers.pop('X-CSRF-Token',None);assert post(client,path,body).status_code==403
    sign_in('planner');assert client.get(path).status_code==403
    sign_in('restricted');assert client.get(path).status_code==403
    sign_in('engineer');assert post(client,path,body).status_code==200
    assert post(client,path+'/preview',{'expected_plan_version':1,'match_id':'unknown'}).status_code==404
    assert post(client,path+'/preview',{'expected_plan_version':2,'match_id':'unknown'}).status_code==409
    from backend.main import app
    from backend.security import current_user
    with SessionLocal() as db:
        scoped=db.scalar(select(User).where(User.email=='restricted@sentinel.local'));scoped.role='engineer'
        app.dependency_overrides[current_user]=lambda:scoped
        try:
            assert client.get(path).status_code==404
            assert post(client,path,body).status_code==404
            assert client.get(path+'/history').status_code==404
            assert post(client,path+'/preview',{'expected_plan_version':1,'match_id':'unknown'}).status_code==404
        finally:app.dependency_overrides.pop(current_user,None)
    client.cookies.clear();assert client.get(path).status_code==401


def test_old_rule_binding_and_different_match_cannot_be_mixed(client,sign_in):
    asset,rule,path,body=setup_plan(client,sign_in);mid=match(client,rule,asset);assert post(client,path,body).status_code==200
    other,other_rule,other_path,other_body=setup_plan(client,sign_in);other_mid=match(client,other_rule,other)
    assert post(client,path+'/preview',{'expected_plan_version':1,'match_id':other_mid}).status_code==404
    with SessionLocal() as db:
        from backend.database import ConditionRule
        r=db.get(ConditionRuleRevision,(rule['id'],1));db.add(ConditionRuleRevision(rule_id=rule['id'],version=2,name='New rule revision',settings=r.settings,
            reason='Synthetic changed rule fixture',actor_id=r.actor_id,actor_name=r.actor_name));db.get(ConditionRule,rule['id']).version=2;db.commit()
    assert post(client,path,{**body,'expected_version':1}).status_code==409
    old=post(client,path+'/preview',{'expected_plan_version':1,'match_id':mid});assert old.status_code==200 and not old.json()['plan_rule_is_current']
    assert post(client,path,{**body,'expected_version':1,'expected_rule_version':2}).status_code==200
    assert post(client,path+'/preview',{'expected_plan_version':2,'match_id':mid}).status_code==409


def test_plan_history_pagination_and_literal_recipient_search(client,sign_in):
    _,rule,path,body=setup_plan(client,sign_in);assert post(client,path,body).status_code==200
    with SessionLocal() as db:
        first=db.get(Plan,(rule['id'],1))
        for version in range(2,62):db.add(Plan(rule_id=rule['id'],version=version,rule_version=1,name='History fixture',recipients=first.recipients,actor_id=first.actor_id,actor_name=first.actor_name,reason='Synthetic pagination fixture'))
        db.commit()
    first=client.get(path+'/history').json();last=client.get(path+'/history',params={'before_version':first['next_before_version']}).json()
    assert len(first['items'])==50 and len(last['items'])==11 and last['next_before_version'] is None
    assert [p['version'] for p in first['items']+last['items']]==list(range(61,0,-1))
    assert client.get(path,params={'recipient_name':'%'}).json()['recipients']==[]


def test_real_address_indicator_never_returns_address(client,sign_in):
    asset,rule,path,body=setup_plan(client,sign_in);mid=match(client,rule,asset)
    with SessionLocal() as db:
        person=db.get(User,body['recipient_ids'][0]);previous=person.email;person.email='notification-fixture@example.com';db.commit()
    try:
        assert post(client,path,body).status_code==200
        answer=post(client,path+'/preview',{'expected_plan_version':1,'match_id':mid})
        assert answer.json()['eligible_configured_count']==1 and 'notification-fixture@example.com' not in answer.text
    finally:
        with SessionLocal() as db:db.get(User,body['recipient_ids'][0]).email=previous;db.commit()
