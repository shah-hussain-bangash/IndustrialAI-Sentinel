import uuid

import pytest
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from backend.database import Asset, Audit, Document, Site, SiteMembership, User, SessionLocal, stable_site_id
from backend.seed import SITES


def test_site_directory_authorization_and_stable_ids(client,sign_in):
    assert client.get("/api/sites").status_code==401
    sign_in()
    directory=client.get("/api/sites").json()["items"]
    assert len(directory)==2
    assert {s["id"] for s in directory}=={stable_site_id(name) for name in SITES}
    sites={s["name"]:s["id"] for s in directory}
    assert all(a["site_id"]==sites[a["site"]] for a in client.get("/api/assets").json())
    assert all(d["site_id"]==sites[d["site"]] for d in client.get("/api/documents").json())
    assert all(e["site_id"]==sites[e["site"]] for e in client.get("/api/activity").json())
    sign_in("restricted")
    assert [s["name"] for s in client.get("/api/sites").json()["items"]]==[SITES[1]]
    assert client.get("/api/auth/me").json()["user"]["site_ids"]==[sites[SITES[1]]]


def test_admin_display_update_preserves_identity_and_alias(client,sign_in):
    sign_in("admin")
    site=client.get("/api/sites").json()["items"][0]
    assets=client.get("/api/assets").json()
    body={"expected_version":site["version"],"display_name":"Reviewed site display"}
    result=client.patch("/api/sites/"+site["id"],json=body)
    assert result.status_code==200 and result.json()["id"]==site["id"]
    assert result.json()["name"]==site["name"]
    assert result.json()["display_name"]==body["display_name"]
    assert result.json()["version"]==site["version"]+1
    assert client.patch("/api/sites/"+site["id"],json=body).status_code==409
    assert [(a["id"],a["site_id"],a["site"]) for a in client.get("/api/assets").json()]==[(a["id"],a["site_id"],a["site"]) for a in assets]
    assert any(e["action"]=="Site display updated" and e["site_id"]==site["id"] for e in client.get("/api/activity").json())


def test_site_mutations_require_role_csrf_and_valid_display(client,sign_in):
    sign_in()
    site=client.get("/api/sites").json()["items"][0]
    body={"expected_version":site["version"],"display_name":"Changed"}
    assert client.patch("/api/sites/"+site["id"],json=body).status_code==403
    sign_in("admin")
    assert client.patch("/api/sites/"+site["id"],json={**body,"display_name":"   "}).status_code==422
    assert client.patch("/api/sites/"+site["id"],json={**body,"name":"rename alias"}).status_code==422
    client.headers.pop("X-CSRF-Token")
    assert client.patch("/api/sites/"+site["id"],json=body).status_code==403


def test_canonical_memberships_override_forged_legacy_json(client,sign_in):
    sign_in("restricted")
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email=="restricted@sentinel.local"))
        original=user.sites
        db.execute(update(User).where(User.id==user.id).values(sites=SITES).execution_options(synchronize_session=False));db.commit()
    try:
        assert all(a["site"]==SITES[1] for a in client.get("/api/assets").json())
        assert client.get("/api/assets",params={"site":SITES[0]}).status_code==404
        assert [s["name"] for s in client.get("/api/sites").json()["items"]]==[SITES[1]]
    finally:
        with SessionLocal() as db:
            db.execute(update(User).where(User.id==user.id).values(sites=original));db.commit()


@pytest.mark.parametrize("model,values",[
    (Asset,{"tag":"FK-"+uuid.uuid4().hex[:8],"name":"Wrong site fixture","kind":"Pump","location":"Test"}),
    (Document,{"title":"Wrong site fixture","filename":"test.txt","pages":["test"],"checksum":"0"*64}),
    (Audit,{"actor":"Test","action":"Invalid site pair","target":"fixture"}),
])
def test_database_rejects_mismatched_site_identity(client,model,values):
    with SessionLocal() as db:
        site0=db.scalar(select(Site).where(Site.name==SITES[0]))
        site1=db.scalar(select(Site).where(Site.name==SITES[1]))
        with pytest.raises(IntegrityError):
            db.execute(insert(model).values(**values,site=site0.name,site_id=site1.id));db.commit()


def test_admin_cannot_edit_an_unassigned_site(client,sign_in):
    sign_in("admin")
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email=="admin@sentinel.local"))
        old=user.sites;user.sites=[SITES[0]];db.commit()
        foreign=db.scalar(select(Site).where(Site.name==SITES[1]))
    try:
        assert client.patch("/api/sites/"+foreign.id,json={"expected_version":foreign.version,"display_name":"Blocked"}).status_code==404
    finally:
        with SessionLocal() as db:db.get(User,user.id).sites=old;db.commit()
