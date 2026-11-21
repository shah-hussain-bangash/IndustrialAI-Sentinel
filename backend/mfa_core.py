"""RFC 6238 TOTP, encrypted secret storage and replay-resistant code consumption."""
import base64
import hashlib
import hmac
import os
import re
import struct
from pathlib import Path
from cryptography.fernet import Fernet,InvalidToken
from fastapi import HTTPException
from sqlalchemy import update
from .database import DATA,MfaCredential,MfaPolicy

def cipher():
    key=os.getenv('SENTINEL_MFA_KEY','')
    if not key:
        path=Path(os.getenv('SENTINEL_MFA_KEY_FILE',str(DATA/'security'/'mfa.key')))
        try:key=path.read_bytes().strip()
        except OSError:raise HTTPException(503,'MFA encryption key is unavailable. Ask the server administrator to restore the private MFA key.')
    try:return Fernet(key)
    except (ValueError,TypeError):raise HTTPException(503,'MFA encryption key is invalid. Restore the original private MFA key; do not generate a replacement for existing enrollments.')

def decrypt(value):
    try:return cipher().decrypt(value.encode()).decode()
    except InvalidToken:raise HTTPException(503,'MFA secret cannot be decrypted. Restore the original private MFA encryption key.')

def totp(secret,step,digits=6):
    key=base64.b32decode(secret+'='*((8-len(secret)%8)%8))
    digest=hmac.new(key,struct.pack('>Q',step),hashlib.sha1).digest()
    offset=digest[-1]&15
    return str((struct.unpack('>I',digest[offset:offset+4])[0]&0x7fffffff)%(10**digits)).zfill(digits)

def code_hash(value):return hashlib.sha256(value.encode()).hexdigest()

def consume(db,row,code,t,allow_backup=True):
    code=re.sub(r'\s+','',code)
    values={}
    if re.fullmatch(r'\d{6}',code):
        secret=decrypt(row.secret_encrypted)
        matched=next((step for step in (int(t//30),int(t//30)-1,int(t//30)+1) if step>row.last_step and hmac.compare_digest(totp(secret,step),code)),None)
        if matched is None:raise HTTPException(400,'Code is incorrect, expired or already used. Wait for a fresh code and try again.')
        values['last_step']=matched
    elif allow_backup and row.enabled:
        normalized=code.replace('-','').upper()
        if not re.fullmatch(r'[A-F0-9]{32}',normalized):raise HTTPException(400,'Enter a six-digit authenticator code or an unused backup code.')
        digest=code_hash(normalized)
        if not any(hmac.compare_digest(digest,v) for v in row.recovery_hashes):raise HTTPException(400,'Backup code is invalid or has already been used.')
        values['recovery_hashes']=[v for v in row.recovery_hashes if not hmac.compare_digest(v,digest)]
    else:raise HTTPException(400,'Enter the six-digit code from your authenticator app.')
    result=db.execute(update(MfaCredential).where(MfaCredential.user_id==row.user_id,MfaCredential.version==row.version).values(**values,version=row.version+1).execution_options(synchronize_session=False))
    if result.rowcount!=1:raise HTTPException(409,'This code or account was used by another request. Try a fresh code.')
    return values

def required(db):
    row=db.get(MfaPolicy,'primary')
    return bool(row and row.required)
