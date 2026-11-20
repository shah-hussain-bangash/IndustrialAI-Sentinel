"""Permitted site identities and administrator-managed display metadata."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .database import Asset, Audit, Document, Sensor, Site, SiteMembership, User, engine
from .security import allow, current_user, get_db


class SiteDisplay(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    display_name: str = Field(min_length=1,max_length=100)

    @field_validator("display_name")
    @classmethod
    def label(cls,value):
        if not value.strip():
            raise ValueError("Display name cannot be blank.")
        return value.strip()


def create_site_router():
    router = APIRouter(prefix="/api/sites",tags=["Site identities"])

    def permitted(db,user,id=None):
        query=select(Site).join(SiteMembership,Site.id==SiteMembership.site_id).where(SiteMembership.user_id==user.id)
        if id: query=query.where(Site.id==id)
        return list(db.scalars(query.order_by(Site.name)))

    def serialize(site,db):
        return {"id":site.id,"name":site.name,"display_name":site.display_name,"timezone":site.timezone,"version":site.version,"assets":db.scalar(select(func.count()).select_from(Asset).where(Asset.site_id==site.id)),"sensors":db.scalar(select(func.count()).select_from(Sensor).join(Asset,Sensor.asset_id==Asset.id).where(Asset.site_id==site.id)),"documents":db.scalar(select(func.count()).select_from(Document).where(Document.site_id==site.id))}

    @router.get("")
    def directory(user:User=Depends(current_user),db:Session=Depends(get_db)):
        return {"items":[serialize(site,db) for site in permitted(db,user)],"database":engine.dialect.name,"scope":"Canonical site memberships govern access. Legacy site names remain compatible aliases."}

    @router.patch("/{id}")
    def display(id:str,body:SiteDisplay,user:User=Depends(current_user),db:Session=Depends(get_db)):
        allow(user,"admin")
        sites=permitted(db,user,id)
        if not sites: raise HTTPException(404,"Site not available in your workspace.")
        site=sites[0]
        changed=db.execute(update(Site).where(Site.id==id,Site.version==body.expected_version).values(display_name=body.display_name,version=Site.version+1).execution_options(synchronize_session=False))
        if changed.rowcount!=1: raise HTTPException(409,"This site changed. Refresh before updating its display name.")
        db.add(Audit(site=site.name,site_id=site.id,actor=user.name,action="Site display updated",target=site.id,details=f"Display metadata version {body.expected_version+1}. Canonical name, membership and equipment links unchanged."))
        db.commit();db.refresh(site)
        return serialize(site,db)

    return router
