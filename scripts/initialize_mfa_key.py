"""Create an installation-private encryption key without printing it."""
import os
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT/'.env',override=False)
from backend.database import DATA
from cryptography.fernet import Fernet
path=Path(os.getenv('SENTINEL_MFA_KEY_FILE',str(DATA/'security'/'mfa.key')))
if os.getenv('SENTINEL_MFA_KEY'):
    Fernet(os.environ['SENTINEL_MFA_KEY'].encode());print('MFA_KEY=EXISTING_ENVIRONMENT_KEY')
else:
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        from sqlalchemy import inspect,text
        from backend.database import engine
        if inspect(engine).has_table('mfa_credentials'):
            with engine.connect() as connection:
                if connection.execute(text('SELECT count(*) FROM mfa_credentials WHERE enabled=1')).scalar():
                    raise SystemExit('The private MFA key is missing but enrolled authenticators exist. Restore the original key; no replacement was generated.')
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(descriptor,'wb') as output:output.write(Fernet.generate_key())
        print('MFA_KEY=CREATED_PRIVATELY')
    else:
        Fernet(path.read_bytes().strip());print('MFA_KEY=EXISTING_KEY_PRESERVED')
print('Back up the private MFA key separately in secure storage before enrolling administrators. Never commit or share it.')
