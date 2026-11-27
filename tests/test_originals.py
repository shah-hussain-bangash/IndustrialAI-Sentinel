import hashlib
import io
import sqlite3
import uuid

import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from sqlalchemy import select, func, inspect, event
from sqlalchemy.exc import IntegrityError

from backend.database import Audit, Document, DocumentOriginal, SessionLocal, engine
from backend.seed import SITES
from backend import recovery
from test_sensor_upgrade import environment, legacy, run


TEXT=b"Original archive validation procedure. Review pump condition and retain source evidence before maintenance.\n"


def upload(client,name="archive.txt",data=TEXT,key=None,title=None):
    return client.post("/api/documents/upload",data={"site":SITES[0],"kind":"Pump","title":title or "Archive fixture "+uuid.uuid4().hex[:8]},files={"file":(name,data,"application/octet-stream")},headers={"Idempotency-Key":key or str(uuid.uuid4())})


def pdf():
    writer=PdfWriter();page=writer.add_blank_page(width=300,height=300)
    font=DictionaryObject({NameObject("/Type"):NameObject("/Font"),NameObject("/Subtype"):NameObject("/Type1"),NameObject("/BaseFont"):NameObject("/Helvetica")})
    page[NameObject("/Resources")]=DictionaryObject({NameObject("/Font"):DictionaryObject({NameObject("/F1"):writer._add_object(font)})})
    stream=DecodedStreamObject();stream.set_data(b"BT /F1 12 Tf 20 250 Td (Original archive procedure for pump maintenance and evidence review.) Tj ET")
    page[NameObject("/Contents")]=writer._add_object(stream)
    output=io.BytesIO();writer.write(output);return output.getvalue()


@pytest.mark.parametrize("name,content,media",[("source.txt",TEXT,"text/plain"),("source.md",TEXT,"text/markdown"),("source.pdf",None,"application/pdf")])
def test_new_upload_retains_exact_bytes_and_returns_scoped_attachment(client,sign_in,name,content,media):
    sign_in();content=content if content is not None else pdf()
    result=upload(client,name,content);assert result.status_code==201,result.text
    id=result.json()["id"];assert result.json()["original_archived"] is True
    detail=client.get("/api/documents/"+id).json()
    assert detail["original_available"] and detail["original_bytes"]==len(content)
    assert detail["checksum"]==hashlib.sha256(content).hexdigest()
    listing=next(d for d in client.get("/api/documents").json() if d["id"]==id)
    assert listing["original_status"]=="archived"
    download=client.get(f"/api/documents/{id}/original")
    assert download.status_code==200 and download.content==content
    assert download.headers["content-type"].startswith(media)
    assert download.headers["content-disposition"].startswith("attachment;")
    assert "no-store" in download.headers["cache-control"]
    assert download.headers["x-content-type-options"]=="nosniff"
    assert download.headers["x-document-sha256"]==detail["checksum"]
    with SessionLocal() as db:
        original=db.get(DocumentOriginal,id)
        assert "content" in inspect(original).unloaded
        assert original.byte_size==len(content)


def test_original_access_requires_session_and_canonical_site_membership(client,sign_in):
    sign_in();id=upload(client).json()["id"]
    sign_in("restricted");assert client.get(f"/api/documents/{id}/original").status_code==404
    sign_in("technician");assert client.get(f"/api/documents/{id}/original").status_code==200
    assert upload(client).status_code==403
    client.post("/api/auth/logout")
    assert client.get(f"/api/documents/{id}/original").status_code==401


def test_idempotency_covers_filename_and_prevents_duplicate_originals(client,sign_in):
    sign_in();key=str(uuid.uuid4());title="Original idempotency fixture"
    first=upload(client,key=key,title=title);second=upload(client,key=key,title=title)
    assert first.status_code==second.status_code==201 and first.json()==second.json()
    assert upload(client,name="renamed.txt",key=key,title=title).status_code==409
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(DocumentOriginal).where(DocumentOriginal.document_id==first.json()["id"]))==1


def test_legacy_document_does_not_fabricate_an_original(client,sign_in):
    sign_in()
    with SessionLocal() as db:
        doc=Document(title="Legacy original missing",filename="legacy.txt",site=SITES[0],kind="Pump",pages=[TEXT.decode()],checksum=hashlib.sha256(TEXT).hexdigest());db.add(doc);db.commit();id=doc.id
    detail=client.get("/api/documents/"+id).json()
    assert not detail["original_available"] and detail["original_status"]=="not_retained"
    assert client.get(f"/api/documents/{id}/original").status_code==404
    assert detail["pages"]==[TEXT.decode()]


def test_filename_paths_and_non_ascii_are_attachment_safe(client,sign_in):
    sign_in();result=upload(client,name="../folder/ø source.txt");assert result.status_code==201,result.text
    id=result.json()["id"]
    detail=client.get("/api/documents/"+id).json();assert detail["filename"]=="ø source.txt"
    response=client.get(f"/api/documents/{id}/original")
    assert "%C3%B8%20source.txt" in response.headers["content-disposition"]
    assert "../" not in response.headers["content-disposition"]
    assert upload(client,name="x"*241+".txt").status_code==422


def test_failed_upload_does_not_commit_metadata_or_original(client,sign_in):
    sign_in();title="Original rollback "+uuid.uuid4().hex
    def fail(mapper,connection,target):
        if target.action=="Document indexed":raise RuntimeError("intentional archive audit failure")
    event.listen(Audit,"before_insert",fail)
    try:
        with pytest.raises(RuntimeError):upload(client,title=title)
    finally:event.remove(Audit,"before_insert",fail)
    with SessionLocal() as db:assert not db.scalar(select(Document).where(Document.title==title))
    assert upload(client,name="bad.pdf",data=b"%PDF-invalid").status_code==422
    assert upload(client,name="bad.exe").status_code==422
    assert upload(client,data=b"short").status_code==422


def test_download_and_recovery_reject_changed_original_bytes(client,sign_in,tmp_path):
    sign_in();id=upload(client).json()["id"]
    with SessionLocal() as db:
        original=db.get(DocumentOriginal,id);original.content=b"x"*len(TEXT);db.commit()
    try:
        assert client.get(f"/api/documents/{id}/original").status_code==409
        if engine.dialect.name=="sqlite":
            report=recovery.run_recovery(engine.url.database,tmp_path/"recovery",str(uuid.uuid4()))
            assert report["status"]=="failed"
    finally:
        with SessionLocal() as db:db.get(DocumentOriginal,id).content=TEXT;db.commit()


def test_recovery_verifies_originals_and_old_format_one_manifests(client,sign_in,tmp_path):
    sign_in();id=upload(client).json()["id"]
    if engine.dialect.name!="sqlite":
        assert client.get(f"/api/documents/{id}/original").content==TEXT
        return
    root=tmp_path/"recovery";job=str(uuid.uuid4())
    report=recovery.run_recovery(engine.url.database,root,job)
    assert report["status"]=="passed" and report["original_files_verified"]>=1
    assert report["documents_without_original"]>=6
    restored=root/"runs"/job/"restored/snapshot.db"
    with sqlite3.connect(restored) as db:assert db.execute("SELECT content FROM document_originals WHERE document_id=?",(id,)).fetchone()[0]==TEXT
    # Old manifests have no separate originals inventory but still require full DB checks.
    import json
    bundle=root/"runs"/job/"backup";manifest=bundle/"manifest.json"
    content=json.loads(manifest.read_text(encoding="utf-8"));content.pop("originals");manifest.write_text(json.dumps(content),encoding="utf-8")
    assert recovery.verify_restore(bundle,root/"compat-restored")["original_files_verified"]>=1


def test_original_database_constraints(client,sign_in):
    sign_in()
    for changes in ({"byte_size":0},{"media_type":"application/javascript"},{"checksum":"short"}):
        with SessionLocal() as db:
            doc=Document(title="Constraint fixture",filename="fixture.txt",site=SITES[0],pages=[TEXT.decode()],checksum=hashlib.sha256(TEXT).hexdigest());db.add(doc);db.commit();id=doc.id
        values={"document_id":id,"content":TEXT,"checksum":hashlib.sha256(TEXT).hexdigest(),"byte_size":len(TEXT),"media_type":"text/plain",**changes}
        with SessionLocal() as db:
            db.add(DocumentOriginal(**values))
            with pytest.raises(IntegrityError):db.commit()


def test_revision6_to7_preserves_documents_and_marks_legacy_missing(tmp_path):
    env,path=environment(tmp_path);legacy(env);run(env,"-m","alembic","upgrade","0006")
    with sqlite3.connect(path) as db:
        site_id=db.execute("SELECT id FROM sites LIMIT 1").fetchone()[0]
        import json
        db.execute("INSERT INTO documents (id,title,filename,site,site_id,kind,version,pages,checksum,created) VALUES (?,?,?,?,?,?,?,?,?,?)",("legacy-doc","Legacy source","legacy.txt","Legacy site",site_id,"Pump","1.0",json.dumps([TEXT.decode()]),hashlib.sha256(TEXT).hexdigest(),1.))
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'") if r[0]!="alembic_version"]
        before={t:db.execute(f'SELECT * FROM "{t}" ORDER BY 1').fetchall() for t in tables}
    run(env,"scripts/upgrade_database.py")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0]=="0019"
        for t,rows in before.items():assert db.execute(f'SELECT * FROM "{t}" ORDER BY 1').fetchall()==rows
        assert db.execute("SELECT count(*) FROM document_originals").fetchone()[0]==0
    run(env,"-m","alembic","check")
