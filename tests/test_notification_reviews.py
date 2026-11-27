import uuid
import pytest
from sqlalchemy import select,func
from backend.database import (SessionLocal,NotificationPlanRevision as Plan,NotificationPlanReview as Review,ConditionRule,ConditionRuleRevision,
    User,Audit,AccountLink,Reading,WorkOrder)
from test_live_rules import cleanup_live_fixture
from test_notification_plans import clear_plans,setup_plan
from test_window_reviews import post


def proposal(client,sign_in):
    asset,rule,path,body=setup_plan(client,sign_in)
    sign_in('engineer');saved=post(client,path,body);assert saved.status_code==200,saved.text
    return asset,rule,path,body


def command(plan=1,review=0,head=1):
    return dict(decision='approved',expected_plan_version=plan,expected_rule_version=head,expected_review_version=review,
        reason='Synthetic independent planning review only',confirmed=True)


def test_independent_decision_idempotency_history_and_new_plan_revision(client,sign_in):
    asset,rule,path,body=proposal(client,sign_in)
    assert not client.get(path+'/reviews').json()['can_review']
    assert post(client,path+'/reviews',command()).status_code==403
    sign_in('admin');info=client.get(path+'/reviews').json()
    assert info['can_review'] and info['can_approve'] and info['current_decision'] is None
    assert info['saved_plan']['name']==body['name'] and not info['delivery_enabled']
    key=str(uuid.uuid4());approved=post(client,path+'/reviews',command(),key);assert approved.status_code==200,approved.text
    assert approved.json()['current_decision']=='approved'
    assert post(client,path+'/reviews',command(),key).json()==approved.json()
    assert post(client,path+'/reviews',{**command(),'reason':'Changed note'},key).status_code==409
    assert post(client,path+'/reviews',command()).status_code==409
    rejected=post(client,path+'/reviews',{**command(review=1),'decision':'rejected'});assert rejected.json()['current_decision']=='rejected'
    sign_in('engineer');assert post(client,path,{**body,'expected_version':1,'name':'Revised notification plan'}).status_code==200
    changed=client.get(path+'/reviews').json();assert changed['current_decision'] is None and changed['last_review']['plan_version']==1
    assert [r['state'] for r in changed['items']]==['rejected','approved']
    sign_in('admin');assert post(client,path+'/reviews',command(review=2)).status_code==409
    assert post(client,path+'/reviews',command(plan=2,review=2)).status_code==200
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Review).where(Review.rule_id==rule['id']))==3
        assert db.scalar(select(func.count()).select_from(Audit).where(Audit.action=='Notification plan planning review',Audit.details.contains(rule['id'])))==3


def test_admin_cannot_review_own_revision(client,sign_in):
    _,_,path,body=setup_plan(client,sign_in);assert post(client,path,body).status_code==200
    assert not client.get(path+'/reviews').json()['can_review']
    assert post(client,path+'/reviews',command()).status_code==403


@pytest.mark.parametrize('changes',[{'confirmed':False},{'confirmed':1},{'reason':'bad'},{'reason':'line\nbreak'},
    {'expected_plan_version':True},{'expected_review_version':-1},{'decision':'active'},{'destination':'person@example.com'},{'activate':True}])
def test_review_validation(client,sign_in,changes):
    _,_,path,_=proposal(client,sign_in);sign_in('admin')
    assert post(client,path+'/reviews',{**command(),**changes}).status_code==422
    assert client.get(path+'/reviews').json()['review_version']==0


def test_current_eligibility_separate_from_historical_planning_decision(client,sign_in):
    _,_,path,body=proposal(client,sign_in);sign_in('admin')
    assert post(client,path+'/reviews',command()).status_code==200
    with SessionLocal() as db:
        person=db.get(User,body['recipient_ids'][0]);old_role=person.role;person.role='disabled';db.commit()
    try:
        current=client.get(path+'/reviews').json()
        assert current['current_decision']=='approved' and not current['recipient_checks'][0]['currently_eligible']
        assert not current['can_approve'] and not current['delivery_enabled']
        assert post(client,path+'/reviews',command(review=1)).status_code==409
        assert post(client,path+'/reviews',{**command(review=1),'decision':'rejected'}).status_code==200
    finally:
        with SessionLocal() as db:db.get(User,body['recipient_ids'][0]).role=old_role;db.commit()


def test_rule_head_change_blocks_approval_but_allows_rejection_of_exact_plan(client,sign_in):
    _,rule,path,_=proposal(client,sign_in);sign_in('admin')
    with SessionLocal() as db:
        saved=db.get(ConditionRuleRevision,(rule['id'],1))
        db.add(ConditionRuleRevision(rule_id=rule['id'],version=2,name='Changed rule head',settings=saved.settings,reason='Synthetic rule revision',actor_id=saved.actor_id,actor_name=saved.actor_name));db.get(ConditionRule,rule['id']).version=2;db.commit()
    assert post(client,path+'/reviews',command()).status_code==409
    assert post(client,path+'/reviews',command(head=2)).status_code==409
    response=post(client,path+'/reviews',{**command(head=2),'decision':'rejected'});assert response.status_code==200,response.text
    assert response.json()['saved_plan']['rule_version']==1 and not response.json()['plan_rule_is_current']


def test_review_access_csrf_site_and_no_plan(client,sign_in):
    _,_,empty,_=setup_plan(client,sign_in);assert client.get(empty+'/reviews').status_code==409
    _,_,path,_=proposal(client,sign_in);sign_in('admin');client.headers.pop('X-CSRF-Token',None)
    assert post(client,path+'/reviews',command()).status_code==403
    sign_in('planner');assert client.get(path+'/reviews').status_code==403
    sign_in('admin')
    from backend.main import app
    from backend.security import current_user
    with SessionLocal() as db:
        scoped=db.scalar(select(User).where(User.email=='restricted@sentinel.local'));scoped.role='admin'
        app.dependency_overrides[current_user]=lambda:scoped
        try:
            assert client.get(path+'/reviews').status_code==404
            assert post(client,path+'/reviews',command()).status_code==404
        finally:app.dependency_overrides.pop(current_user,None)
    client.cookies.clear();assert client.get(path+'/reviews').status_code==401


def test_planning_review_does_not_enable_delivery_or_change_operations(client,sign_in):
    _,_,path,_=proposal(client,sign_in);sign_in('admin')
    with SessionLocal() as db:before=[db.scalar(select(func.count()).select_from(m)) for m in (AccountLink,Reading,WorkOrder)]
    response=post(client,path+'/reviews',command());assert response.status_code==200
    assert not response.json()['delivery_enabled'] and not response.json()['saved_plan']['active']
    assert not response.json()['recipient_checks'][0]['email_address_configured']
    assert '@sentinel.local' not in response.text
    with SessionLocal() as db:assert before==[db.scalar(select(func.count()).select_from(m)) for m in (AccountLink,Reading,WorkOrder)]


def test_review_history_pagination(client,sign_in):
    _,rule,path,_=proposal(client,sign_in)
    with SessionLocal() as db:
        admin=db.scalar(select(User).where(User.email=='admin@sentinel.local'))
        for version in range(1,62):db.add(Review(rule_id=rule['id'],version=version,plan_version=1,state='approved' if version%2 else 'rejected',actor_id=admin.id,actor_name=admin.name,reason='Synthetic history fixture'))
        db.commit()
    first=client.get(path+'/reviews').json();last=client.get(path+'/reviews',params={'before_version':first['next_before_version']}).json()
    assert len(first['items'])==50 and len(last['items'])==11 and last['next_before_version'] is None
    assert [r['version'] for r in first['items']+last['items']]==list(range(61,0,-1))
