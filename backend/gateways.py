"""Minimal machine ingestion: one asset, hashed credentials, no operational tools."""
import hashlib
import hmac
import re
import secrets
import uuid
from types import SimpleNamespace
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from .database import Asset, Audit, Sensor, TelemetryGateway, User, now
from .security import allow, canonicalize_user, current_user, get_db
from .sensor_events import EventInput, store_event


class GatewayCreate(BaseModel):
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True)
    asset_id:str=Field(min_length=1,max_length=36)
    name:str=Field(min_length=1,max_length=100)
    lifetime_days:int=Field(default=7,ge=1,le=90)


class GatewayVersion(BaseModel):
    model_config=ConfigDict(extra="forbid")
    expected_version:int=Field(ge=1)


class GatewayRotation(GatewayVersion):
    lifetime_days:int=Field(default=7,ge=1,le=90)


class GatewayEvent(EventInput):
    source:Literal["gateway"]="gateway"


class GatewayBatch(BaseModel):
    model_config=ConfigDict(extra="forbid")
    records:list[GatewayEvent]=Field(min_length=1,max_length=500)


def issue(id):
    token="sgw."+id+"."+secrets.token_urlsafe(32)
    return token,hashlib.sha256(token.encode()).hexdigest()


def metadata(gateway,asset):
    return {k:getattr(gateway,k) for k in ("id","asset_id","issuer_id","name","version","created","expires","last_used","accepted_batches","revoked_at")} | {"status":"expired" if gateway.status=="active" and gateway.expires<=now() else gateway.status,"asset_tag":asset.tag,"site":asset.site,"credential_hint":"sgw."+gateway.id[:8]+"…","scope":"sensor events for this asset only"}


def gateway_identity(authorization:str=Header(default="",max_length=200),db:Session=Depends(get_db)):
    invalid=HTTPException(401,"Gateway credential is invalid, expired or unavailable.")
    if not authorization.startswith("Bearer "):raise invalid
    token=authorization[7:]
    if not re.fullmatch(r"sgw\.[0-9a-f-]{36}\.[A-Za-z0-9_-]{43}",token):raise invalid
    id=token.split(".")[1]
    try:
        if str(uuid.UUID(id))!=id:raise invalid
    except ValueError:raise invalid
    gateway=db.get(TelemetryGateway,id)
    if not gateway or not hmac.compare_digest(gateway.token_hash,hashlib.sha256(token.encode()).hexdigest()) or gateway.status!="active" or gateway.expires<=now():raise invalid
    issuer=db.get(User,gateway.issuer_id);asset=db.get(Asset,gateway.asset_id)
    if not issuer or not asset or issuer.role!="admin":raise invalid
    canonicalize_user(issuer,db)
    if asset.site not in issuer.sites:raise invalid
    return gateway


def create_gateway_router(accessible_assets,asset_for,idempotent,finish):
    router=APIRouter(tags=["Telemetry gateway credentials"])

    @router.get("/api/gateways")
    def listing(user:User=Depends(current_user),db:Session=Depends(get_db)):
        allow(user,"admin");assets=accessible_assets(db,user,None);by_id={a.id:a for a in assets}
        rows=db.scalars(select(TelemetryGateway).where(TelemetryGateway.asset_id.in_(by_id)).order_by(TelemetryGateway.created.desc()).limit(100)).all()
        return {"items":[metadata(g,by_id[g.asset_id]) for g in rows],"assets":[{"id":a.id,"tag":a.tag,"name":a.name,"site":a.site} for a in assets],"scope":"HTTP event ingestion only; no PLC, maintenance approval or original-file access."}

    @router.post("/api/gateways",status_code=201)
    def create(body:GatewayCreate,request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
        allow(user,"admin");asset=asset_for(db,user,body.asset_id)
        key,hashed,old=idempotent(db,request,user,body.model_dump())
        if old is not None:return {**old,"credential":None,"credential_notice":"Credential was already issued. Rotate it if the original response was lost."}
        id=str(uuid.uuid4());token,token_hash=issue(id);clock=now()
        gateway=TelemetryGateway(id=id,asset_id=asset.id,issuer_id=user.id,name=body.name,token_hash=token_hash,status="active",version=1,created=clock,expires=clock+body.lifetime_days*86400,accepted_batches=0)
        db.add(gateway);db.flush()
        db.add(Audit(site=asset.site,actor=user.name,action="Gateway credential issued",target=asset.tag,details=f"Gateway {id}; asset-scoped event intake; expires {gateway.expires}; plaintext not retained."))
        # Persist only metadata. Plaintext credentials must never enter idempotency receipts.
        receipt=finish(db,key,hashed,{"gateway":metadata(gateway,asset),"credential_available_once":True})
        return {**receipt,"credential":token,"credential_notice":"Displayed once. Store it privately; rotation invalidates the earlier credential."}

    @router.post("/api/gateways/{id}/rotate")
    def rotate(id:str,body:GatewayRotation,request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
        allow(user,"admin");gateway=db.get(TelemetryGateway,id)
        if not gateway:raise HTTPException(404,"Gateway not found.")
        asset=asset_for(db,user,gateway.asset_id)
        key,hashed,old=idempotent(db,request,user,body.model_dump())
        if old is not None:return {**old,"credential":None,"credential_notice":"Rotation was already completed. Issue another rotation if the response was lost."}
        token,token_hash=issue(id)
        changed=db.execute(update(TelemetryGateway).where(TelemetryGateway.id==id,TelemetryGateway.version==body.expected_version,TelemetryGateway.status=="active").values(token_hash=token_hash,issuer_id=user.id,expires=now()+body.lifetime_days*86400,version=TelemetryGateway.version+1).execution_options(synchronize_session=False))
        if changed.rowcount!=1:raise HTTPException(409,"Gateway changed or was revoked. Refresh before rotating.")
        db.refresh(gateway)
        db.add(Audit(site=asset.site,actor=user.name,action="Gateway credential rotated",target=asset.tag,details=f"Gateway {id}; credential version {gateway.version}; prior token invalidated."))
        receipt=finish(db,key,hashed,{"gateway":metadata(gateway,asset),"credential_available_once":True})
        return {**receipt,"credential":token,"credential_notice":"Displayed once; the previous credential no longer works."}

    @router.post("/api/gateways/{id}/revoke")
    def revoke(id:str,body:GatewayVersion,request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
        allow(user,"admin");gateway=db.get(TelemetryGateway,id)
        if not gateway:raise HTTPException(404,"Gateway not found.")
        asset=asset_for(db,user,gateway.asset_id)
        key,hashed,old=idempotent(db,request,user,body.model_dump())
        if old is not None:return old
        changed=db.execute(update(TelemetryGateway).where(TelemetryGateway.id==id,TelemetryGateway.version==body.expected_version,TelemetryGateway.status=="active").values(status="revoked",revoked_at=now(),version=TelemetryGateway.version+1).execution_options(synchronize_session=False))
        if changed.rowcount!=1:raise HTTPException(409,"Gateway changed or was already revoked. Refresh.")
        db.refresh(gateway)
        db.add(Audit(site=asset.site,actor=user.name,action="Gateway credential revoked",target=asset.tag,details=f"Gateway {id}; version {gateway.version}; event access revoked."))
        return finish(db,key,hashed,{"gateway":metadata(gateway,asset)})

    @router.get("/api/gateway-identity")
    def identity(gateway:TelemetryGateway=Depends(gateway_identity),db:Session=Depends(get_db)):
        asset=db.get(Asset,gateway.asset_id)
        sensors=db.scalars(select(Sensor).where(Sensor.asset_id==asset.id).order_by(Sensor.channel)).all()
        return {"gateway_id":gateway.id,"name":gateway.name,"asset_id":asset.id,"asset_tag":asset.tag,"credential_version":gateway.version,"sensors":[{"id":s.id,"channel":s.channel,"unit":s.unit} for s in sensors],"scope":"Independent event batches only. No automatic snapshot publication."}

    @router.post("/api/gateway-events/batches",status_code=201)
    def ingest(body:GatewayBatch,request:Request,gateway:TelemetryGateway=Depends(gateway_identity),db:Session=Depends(get_db)):
        asset=db.get(Asset,gateway.asset_id);sensors={s.id:s for s in db.scalars(select(Sensor).where(Sensor.asset_id==asset.id))}
        if any(r.sensor_id not in sensors for r in body.records):raise HTTPException(404,"A submitted sensor is outside this gateway's asset scope.")
        principal=SimpleNamespace(id=f"gateway:{gateway.id}:v{gateway.version}",name=f"Gateway {gateway.name} [{gateway.id} v{gateway.version}]")
        key,hashed,old=idempotent(db,request,principal,body.model_dump())
        if old is not None:return old
        try:
            changed=db.execute(update(TelemetryGateway).where(TelemetryGateway.id==gateway.id,TelemetryGateway.version==gateway.version,TelemetryGateway.status=="active",TelemetryGateway.expires>now(),TelemetryGateway.token_hash==gateway.token_hash).values(last_used=now(),accepted_batches=TelemetryGateway.accepted_batches+1).execution_options(synchronize_session=False))
            if changed.rowcount!=1:raise HTTPException(401,"Gateway credential changed or expired. Retry with a current credential.")
            inserted=duplicates=0;ids=[];clock=now()
            for record in body.records:
                event,is_new=store_event(db,record.model_copy(update={"source":"gateway:"+gateway.id}),sensors[record.sensor_id],asset,principal,clock)
                inserted+=int(is_new);duplicates+=int(not is_new);ids.append(event.id)
            db.add(Audit(site=asset.site,actor=principal.name,action="Gateway batch accepted",target=asset.tag,details=f"Gateway {gateway.id}; credential version {gateway.version}; {inserted} new events, {duplicates} duplicates; no snapshot publication."))
            return finish(db,key,hashed,{"gateway_id":gateway.id,"inserted":inserted,"duplicates":duplicates,"event_ids":ids,"snapshot_projection":False})
        except (IntegrityError,OperationalError):
            db.rollback();raise HTTPException(409,"Concurrent gateway ingestion conflicted. Retry with the same request key.")
        except Exception:
            db.rollback();raise

    return router
