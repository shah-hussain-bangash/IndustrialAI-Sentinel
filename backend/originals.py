"""Original document metadata and permission-checked attachment downloads."""
import hashlib
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from .database import Document, DocumentOriginal, User
from .security import current_user, get_db, site_allowed


def filename(value):
    name = (value or "document").replace("\\","/").rsplit("/",1)[-1]
    name = "".join(c for c in name if c.isprintable()).strip()
    if not name or len(name)>240:
        raise HTTPException(422,"Choose a filename between 1 and 240 printable characters.")
    return name


def original_metadata(db,doc):
    original=db.get(DocumentOriginal,doc.id)
    return {"original_available":original is not None,"original_bytes":original.byte_size if original else None,
            "original_media_type":original.media_type if original else None,"original_archived_at":original.archived_at if original else None,
            "original_status":"archived" if original else "not_retained"}


def create_original_router():
    router=APIRouter(tags=["Original document files"])

    @router.get("/api/documents/{id}/original")
    def download(id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
        doc=db.get(Document,id)
        if not doc:raise HTTPException(404,"Document not found.")
        site_allowed(user,doc.site)
        original=db.get(DocumentOriginal,id)
        if not original:raise HTTPException(404,"This earlier document has no retained original. Its extracted text remains available.")
        content=original.content
        if len(content)!=original.byte_size or hashlib.sha256(content).hexdigest()!=original.checksum or original.checksum!=doc.checksum:
            raise HTTPException(409,"The archived original failed its integrity check. Download was blocked.")
        return Response(content=content,media_type=original.media_type,headers={
            "Content-Disposition":"attachment; filename*=UTF-8''"+quote(doc.filename,safe=""),
            "Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff","Content-Security-Policy":"sandbox; default-src 'none'",
            "X-Document-SHA256":original.checksum,
        })

    return router
