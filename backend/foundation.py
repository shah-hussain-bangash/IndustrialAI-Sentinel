"""Versioned, site-scoped hierarchy for one organization. No tenant-isolation claim."""
import json
import re
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .database import Organization, Site, SiteMembership, SiteArea, EquipmentSystem, EquipmentPlacement, Asset, Audit, User, stable_site_id
from .security import current_user, get_db, allow


class Labels(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1,max_length=30)
    name: str = Field(min_length=1,max_length=120)

    @field_validator("code")
    @classmethod
    def code_valid(cls,value):
        value=value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{0,29}",value):
            raise ValueError("Use letters, digits, hyphens or underscores in the code.")
        return value

    @field_validator("name")
    @classmethod
    def name_valid(cls,value):
        if not value.strip() or any(ord(c)<32 for c in value):
            raise ValueError("Provide a name without control characters.")
        return value.strip()


class AreaCreate(Labels):
    site_id: str = Field(min_length=1,max_length=36)


class SystemCreate(Labels):
    area_id: str = Field(min_length=1,max_length=36)


class LabelUpdate(Labels):
    expected_version: int = Field(ge=1)


class OrganizationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    name: str = Field(min_length=1,max_length=160)
    description: str = Field(default="",max_length=500)

    @field_validator("name","description")
    @classmethod
    def clean(cls,value,info):
        value=value.strip()
        if info.field_name=="name" and not value or any(ord(c)<32 for c in value):
            raise ValueError("Provide text without control characters.")
        return value


class PlacementUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    system_id: str | None = Field(default=None,max_length=36,min_length=1)


class SiteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_organization_version: int = Field(ge=1)
    name: str = Field(min_length=1,max_length=100)

    @field_validator("name")
    @classmethod
    def clean(cls,value):
        if not value.strip() or any(ord(c)<32 for c in value):raise ValueError("Provide a site name without control characters.")
        return value.strip()


def create_foundation_router(idempotent, finish, asset_for):
    router=APIRouter(prefix="/api/foundation",tags=["Organization and hierarchy"])

    def sites_for(db,user):
        return list(db.scalars(select(Site).join(SiteMembership,Site.id==SiteMembership.site_id).where(SiteMembership.user_id==user.id).order_by(Site.name)))

    def permitted_site(db,user,id):
        site=next((s for s in sites_for(db,user) if s.id==id),None)
        if not site: raise HTTPException(404,"Site not available in your workspace.")
        return site

    def full_admin(db,user):
        return user.role=="admin" and set(s.id for s in sites_for(db,user))==set(db.scalars(select(Site.id)))

    def org_json(row,db,user):
        return dict(id=row.id,name=row.name,description=row.description,configured=bool(row.configured),version=row.version,deployment_scope="single_organization",can_edit=full_admin(db,user))

    def label_json(row):
        result=dict(id=row.id,site_id=row.site_id,code=row.code,name=row.name,version=row.version)
        if isinstance(row,EquipmentSystem):result["area_id"]=row.area_id
        return result

    def audit(db,user,site,action,target,details):
        db.add(Audit(site=site.name,site_id=site.id,actor=user.name,action=action,target=target,details=json.dumps({"actor_id":user.id,**details},sort_keys=True)))

    def commit(db,key,digest,result):
        try:return finish(db,key,digest,result)
        except IntegrityError:
            db.rollback()
            raise HTTPException(409,"The record or code changed. Refresh and review before trying again.")

    @router.get("/organization")
    def organization(user:User=Depends(current_user),db:Session=Depends(get_db)):
        row=db.get(Organization,"primary")
        if not row:raise HTTPException(503,"Organization setup is unavailable. Apply the foundation migration.")
        return org_json(row,db,user)

    @router.patch("/organization")
    def update_organization(body:OrganizationUpdate,request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
        allow(user,"admin")
        if not full_admin(db,user):raise HTTPException(403,"Organization changes require an administrator assigned to every site.")
        key,digest,old=idempotent(db,request,user,body.model_dump())
        if old:return old
        row=db.get(Organization,"primary")
        if not row:raise HTTPException(503,"Apply the foundation migration first.")
        before=dict(name=row.name,description=row.description,version=row.version)
        changed=db.execute(update(Organization).where(Organization.id=="primary",Organization.version==body.expected_version).values(name=body.name,description=body.description,configured=1,version=Organization.version+1).execution_options(synchronize_session=False))
        if changed.rowcount!=1:raise HTTPException(409,"Organization profile changed. Refresh before saving.")
        for site in sites_for(db,user):audit(db,user,site,"Organization profile updated","primary",dict(before=before,after=dict(name=body.name,description=body.description,version=body.expected_version+1)))
        db.refresh(row)
        return commit(db,key,digest,org_json(row,db,user))

    @router.get("/hierarchy")
    def hierarchy(site_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
        site=permitted_site(db,user,site_id)
        areas=list(db.scalars(select(SiteArea).where(SiteArea.site_id==site.id).order_by(SiteArea.code)))
        systems=list(db.scalars(select(EquipmentSystem).where(EquipmentSystem.site_id==site.id).order_by(EquipmentSystem.code)))
        placements={p.asset_id:p for p in db.scalars(select(EquipmentPlacement).where(EquipmentPlacement.site_id==site.id))}
        assets=list(db.scalars(select(Asset).where(Asset.site_id==site.id).order_by(Asset.tag)))
        return dict(site=dict(id=site.id,name=site.display_name),areas=[label_json(a) for a in areas],systems=[label_json(s) for s in systems],equipment=[dict(id=a.id,tag=a.tag,name=a.name,location=a.location,system_id=placements[a.id].system_id if a.id in placements else None,placement_version=placements[a.id].version if a.id in placements else 0) for a in assets],can_configure=user.role=="admin",can_assign=user.role in ("admin","engineer"))

    @router.post("/sites",status_code=201)
    def add_site(body:SiteCreate,request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
        allow(user,"admin")
        # A successful retry must still belong to this company-wide administrator.
        if not full_admin(db,user):raise HTTPException(403,"Creating sites requires an administrator assigned to every site.")
        key,digest,old=idempotent(db,request,user,body.model_dump())
        if old:return old
        if any(site.name.casefold()==body.name.casefold() for site in db.scalars(select(Site))):
            raise HTTPException(409,"This site name already exists.")
        changed=db.execute(update(Organization).where(Organization.id=="primary",Organization.version==body.expected_organization_version).values(version=Organization.version+1).execution_options(synchronize_session=False))
        if changed.rowcount!=1:raise HTTPException(409,"Organization changed. Refresh before creating a site.")
        site=Site(id=stable_site_id(body.name),name=body.name,display_name=body.name,timezone="Asia/Dubai",version=1)
        db.add(site)
        try:db.flush()
        except IntegrityError:
            db.rollback();raise HTTPException(409,"This site name already exists.")
        user.sites=[*user.sites,site.name]
        db.flush()
        audit(db,user,site,"Site created",site.id,dict(name=site.name,creator_membership=user.id,other_memberships="unchanged"))
        return commit(db,key,digest,dict(id=site.id,name=site.name,display_name=site.display_name,timezone=site.timezone,version=1,organization_version=body.expected_organization_version+1))

    @router.post("/areas",status_code=201)
    def add_area(body:AreaCreate,request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
        allow(user,"admin");site=permitted_site(db,user,body.site_id)
        key,digest,old=idempotent(db,request,user,body.model_dump())
        if old:return old
        row=SiteArea(site_id=site.id,code=body.code,name=body.name)
        db.add(row)
        try:db.flush()
        except IntegrityError:
            db.rollback();raise HTTPException(409,"This area code already exists within the site.")
        audit(db,user,site,"Site area created",row.id,dict(code=row.code,name=row.name))
        return commit(db,key,digest,label_json(row))

    @router.post("/systems",status_code=201)
    def add_system(body:SystemCreate,request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
        allow(user,"admin")
        area=db.get(SiteArea,body.area_id)
        if not area:raise HTTPException(404,"Area not available in your workspace.")
        site=permitted_site(db,user,area.site_id)
        key,digest,old=idempotent(db,request,user,body.model_dump())
        if old:return old
        row=EquipmentSystem(site_id=site.id,area_id=area.id,code=body.code,name=body.name)
        db.add(row)
        try:db.flush()
        except IntegrityError:
            db.rollback();raise HTTPException(409,"This system code already exists within the area.")
        audit(db,user,site,"Equipment system created",row.id,dict(area_id=row.area_id,code=row.code,name=row.name))
        return commit(db,key,digest,label_json(row))

    def update_label(model,id,body,request,user,db):
        allow(user,"admin")
        row=db.get(model,id)
        if not row:raise HTTPException(404,"Hierarchy record not available in your workspace.")
        site=permitted_site(db,user,row.site_id)
        key,digest,old=idempotent(db,request,user,body.model_dump())
        if old:return old
        before=label_json(row)
        try:changed=db.execute(update(model).where(model.id==id,model.version==body.expected_version).values(code=body.code,name=body.name,version=model.version+1).execution_options(synchronize_session=False))
        except IntegrityError:
            db.rollback();raise HTTPException(409,"This code already exists in the same parent.")
        if changed.rowcount!=1:raise HTTPException(409,"Hierarchy record changed. Refresh before saving.")
        db.refresh(row);result=label_json(row)
        audit(db,user,site,"Hierarchy labels updated",row.id,dict(before=before,after=result))
        return commit(db,key,digest,result)

    @router.patch("/areas/{id}")
    def update_area(id:str,body:LabelUpdate,request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
        return update_label(SiteArea,id,body,request,user,db)

    @router.patch("/systems/{id}")
    def update_system(id:str,body:LabelUpdate,request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
        return update_label(EquipmentSystem,id,body,request,user,db)

    @router.put("/equipment/{id}/placement")
    def assign_equipment(id:str,body:PlacementUpdate,request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
        allow(user,"admin","engineer")
        asset=asset_for(db,user,id);site=permitted_site(db,user,asset.site_id)
        if body.system_id:
            system=db.get(EquipmentSystem,body.system_id)
            if not system or system.site_id!=site.id:raise HTTPException(404,"System not available within this equipment's site.")
        key,digest,old=idempotent(db,request,user,body.model_dump())
        if old:return old
        row=db.get(EquipmentPlacement,id)
        previous=row.system_id if row else None
        if row:
            changed=db.execute(update(EquipmentPlacement).where(EquipmentPlacement.asset_id==id,EquipmentPlacement.version==body.expected_version).values(system_id=body.system_id,version=EquipmentPlacement.version+1).execution_options(synchronize_session=False))
            if changed.rowcount!=1:raise HTTPException(409,"Equipment placement changed. Refresh before assigning.")
        else:
            if body.expected_version!=0:raise HTTPException(409,"Equipment placement changed. Refresh before assigning.")
            db.add(EquipmentPlacement(asset_id=id,site_id=site.id,system_id=body.system_id,version=1))
        result=dict(asset_id=id,site_id=site.id,system_id=body.system_id,version=body.expected_version+1)
        audit(db,user,site,"Equipment placement updated",asset.tag,dict(previous_system_id=previous,**result))
        return commit(db,key,digest,result)

    return router
