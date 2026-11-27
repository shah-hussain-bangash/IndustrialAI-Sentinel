import uuid
import sqlite3
import pytest
from sqlalchemy import insert, select, delete
from sqlalchemy.exc import IntegrityError
from backend.database import Asset, Audit, EquipmentPlacement, EquipmentSystem, Organization, SessionLocal, SiteArea, User, Site
from test_sensor_upgrade import environment, legacy, run


def key():return {"Idempotency-Key":str(uuid.uuid4())}


def nodes(client,site_id):
    code=uuid.uuid4().hex[:12]
    area=client.post('/api/foundation/areas',json=dict(site_id=site_id,code=code,name='Test area'),headers=key())
    assert area.status_code==201,area.text
    system=client.post('/api/foundation/systems',json=dict(area_id=area.json()['id'],code=code,name='Test system'),headers=key())
    assert system.status_code==201,system.text
    return area.json(),system.json()


def test_organization_auth_permissions_version_and_retry(client,sign_in):
    assert client.get('/api/foundation/organization').status_code==401
    sign_in('engineer')
    org=client.get('/api/foundation/organization').json()
    assert not org['can_edit'] and org['deployment_scope']=='single_organization'
    body=dict(expected_version=org['version'],name='Reviewed company',description='Production foundation fixture')
    assert client.patch('/api/foundation/organization',json=body,headers=key()).status_code==403
    sign_in('admin');headers=key()
    result=client.patch('/api/foundation/organization',json=body,headers=headers)
    assert result.status_code==200,result.text
    assert result.json()['configured'] and result.json()['version']==org['version']+1
    assert client.patch('/api/foundation/organization',json=body,headers=headers).json()==result.json()
    assert client.patch('/api/foundation/organization',json=body,headers=key()).status_code==409
    assert any(e['action']=='Organization profile updated' for e in client.get('/api/activity').json())


def test_partial_admin_cannot_change_company_profile(client,sign_in):
    sign_in('admin')
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email=='admin@sentinel.local'));original=list(user.sites)
        user.sites=original[:1];db.commit();id=user.id
    try:
        org=client.get('/api/foundation/organization').json();assert not org['can_edit']
        assert client.patch('/api/foundation/organization',json=dict(expected_version=org['version'],name='Forbidden'),headers=key()).status_code==403
    finally:
        with SessionLocal() as db:db.get(User,id).sites=original;db.commit()


def test_area_system_and_equipment_lifecycle_preserves_identity(client,sign_in):
    sign_in('admin');sites=client.get('/api/sites').json()['items'];site=sites[0]
    assets=client.get('/api/assets').json();asset=next(a for a in assets if a['site_id']==site['id'])
    area,system=nodes(client,site['id'])
    path='/api/foundation/equipment/'+asset['id']+'/placement'
    hierarchy=client.get('/api/foundation/hierarchy',params={'site_id':site['id']}).json()
    equipment=next(a for a in hierarchy['equipment'] if a['id']==asset['id'])
    body=dict(expected_version=equipment['placement_version'],system_id=system['id']);headers=key()
    placed=client.put(path,json=body,headers=headers);assert placed.status_code==200,placed.text
    assert client.put(path,json=body,headers=headers).json()==placed.json()
    assert client.put(path,json=body,headers=key()).status_code==409
    cleared=client.put(path,json=dict(expected_version=placed.json()['version'],system_id=None),headers=key())
    assert cleared.status_code==200 and cleared.json()['system_id'] is None
    assert cleared.json()['version']==placed.json()['version']+1
    assert client.put(path,json=dict(expected_version=0,system_id=system['id']),headers=key()).status_code==409
    after=client.get('/api/assets/'+asset['id']).json()['asset']
    for field in ['id','site_id','site','location','version']:assert after[field]==asset[field]
    updated=client.patch('/api/foundation/areas/'+area['id'],json=dict(code=area['code'],name='Reviewed area',expected_version=area['version']),headers=key())
    assert updated.status_code==200
    assert client.patch('/api/foundation/areas/'+area['id'],json=dict(code=area['code'],name='Stale overwrite',expected_version=area['version']),headers=key()).status_code==409


def test_hierarchy_boundaries_roles_and_csrf(client,sign_in):
    sign_in('admin');sites=client.get('/api/sites').json()['items'];area0,system0=nodes(client,sites[0]['id']);area1,system1=nodes(client,sites[1]['id'])
    asset=next(a for a in client.get('/api/assets').json() if a['site_id']==sites[0]['id'])
    assert client.put('/api/foundation/equipment/'+asset['id']+'/placement',json=dict(expected_version=0,system_id=system1['id']),headers=key()).status_code==404
    assert client.patch('/api/foundation/systems/'+system0['id'],json=dict(expected_version=1,code='TEST',name='Changed',area_id=area1['id']),headers=key()).status_code==422
    sign_in('restricted')
    permitted=client.get('/api/sites').json()['items'][0]['id'];forbidden=next(s['id'] for s in sites if s['id']!=permitted)
    assert client.get('/api/foundation/hierarchy',params={'site_id':forbidden}).status_code==404
    h=client.get('/api/foundation/hierarchy',params={'site_id':permitted}).json()
    assert not h['can_configure'] and not h['can_assign']
    assert client.post('/api/foundation/areas',json=dict(site_id=permitted,code='FORBIDDEN',name='Blocked'),headers=key()).status_code==403
    sign_in('engineer')
    assert client.post('/api/foundation/systems',json=dict(area_id=area0['id'],code='FORBIDDEN',name='Blocked'),headers=key()).status_code==403
    hierarchy=client.get('/api/foundation/hierarchy',params={'site_id':sites[0]['id']}).json();equipment=next(a for a in hierarchy['equipment'] if a['id']==asset['id'])
    assert client.put('/api/foundation/equipment/'+asset['id']+'/placement',json=dict(expected_version=equipment['placement_version'],system_id=system0['id']),headers=key()).status_code==200
    sign_in('admin');client.headers.pop('X-CSRF-Token')
    assert client.post('/api/foundation/areas',json=dict(site_id=permitted,code='CSRF',name='Blocked'),headers=key()).status_code==403


@pytest.mark.parametrize('changes',[{'name':'   '},{'name':'Bad\x00Name'},{'code':'bad code'},{'code':'../unsafe'}])
def test_labels_reject_invalid_values(client,sign_in,changes):
    sign_in('admin');site=client.get('/api/sites').json()['items'][0]
    assert client.post('/api/foundation/areas',json=dict(site_id=site['id'],**{'code':'VALID','name':'Valid',**changes}),headers=key()).status_code==422


def test_duplicate_codes_and_database_cross_site_integrity(client,sign_in):
    sign_in('admin');sites=client.get('/api/sites').json()['items'];area,system=nodes(client,sites[0]['id'])
    duplicate=client.post('/api/foundation/areas',json=dict(site_id=sites[0]['id'],code=area['code'].lower(),name='Duplicate'),headers=key())
    assert duplicate.status_code==409
    with SessionLocal() as db:
        asset=db.scalar(select(Asset).where(Asset.site_id==sites[1]['id']))
        with pytest.raises(IntegrityError):
            db.execute(insert(EquipmentPlacement).values(asset_id=asset.id,site_id=sites[1]['id'],system_id=system['id'],version=1));db.commit()
        db.rollback()
        with pytest.raises(IntegrityError):
            db.execute(insert(EquipmentSystem).values(id=str(uuid.uuid4()),site_id=sites[1]['id'],area_id=area['id'],code='CROSS',name='Invalid',version=1,created=1));db.commit()


def test_upgrade_0008_preserves_rows_repeats_and_matches_metadata(tmp_path):
    env,path=environment(tmp_path);legacy(env);run(env,'-m','alembic','upgrade','0008')
    with sqlite3.connect(path) as db:
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'") if r[0]!='alembic_version']
        before={name:db.execute(f'SELECT * FROM "{name}" ORDER BY 1').fetchall() for name in tables}
    run(env,'scripts/upgrade_database.py','--check-only')
    run(env,'scripts/upgrade_database.py')
    with sqlite3.connect(path) as db:
        for name,rows in before.items():assert db.execute(f'SELECT * FROM "{name}" ORDER BY 1').fetchall()==rows,name
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='0018'
        assert db.execute('SELECT configured FROM organization').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM equipment_placements').fetchone()[0]==0
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    run(env,'scripts/upgrade_database.py');run(env,'-m','alembic','check')


def test_site_creation_is_versioned_and_grants_creator_only(client,sign_in):
    sign_in('admin')
    original_sites=client.get('/api/auth/me').json()['user']['sites']
    org=client.get('/api/foundation/organization').json();name='New site '+uuid.uuid4().hex[:10]
    body=dict(name=name,expected_organization_version=org['version']);headers=key();new_id=None
    try:
        created=client.post('/api/foundation/sites',json=body,headers=headers)
        assert created.status_code==201,created.text
        new_id=created.json()['id']
        assert client.post('/api/foundation/sites',json=body,headers=headers).json()==created.json()
        assert name in client.get('/api/auth/me').json()['user']['sites']
        h=client.get('/api/foundation/hierarchy',params={'site_id':new_id}).json()
        assert h['areas']==[] and h['equipment']==[]
        assert client.post('/api/foundation/sites',json=dict(name=name+' stale',expected_organization_version=org['version']),headers=key()).status_code==409
        sign_in('engineer')
        assert client.get('/api/foundation/hierarchy',params={'site_id':new_id}).status_code==404
        assert name not in client.get('/api/auth/me').json()['user']['sites']
    finally:
        with SessionLocal() as db:
            admin=db.scalar(select(User).where(User.email=='admin@sentinel.local'));admin.sites=original_sites;db.flush()
            if new_id:
                db.execute(delete(Audit).where(Audit.site_id==new_id));db.execute(delete(Site).where(Site.id==new_id))
            db.commit()
