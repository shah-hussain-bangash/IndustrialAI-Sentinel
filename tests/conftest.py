import os
import tempfile
from pathlib import Path
import pytest

_test_dir = tempfile.TemporaryDirectory(prefix="sentinel-tests-")
os.environ["SENTINEL_DATA_DIR"] = _test_dir.name
os.environ["DEMO_MODE"] = "true"
os.environ["AUTO_CREATE_SCHEMA"] = "true"
os.environ["DEMO_PASSWORD"] = "SentinelDemo!2026"
test_database_url = os.environ.get("SENTINEL_TEST_DATABASE_URL")
if test_database_url:
    from sqlalchemy.engine import make_url
    test_url = make_url(test_database_url)
    if test_url.host not in ("127.0.0.1", "localhost") or not (test_url.database or "").startswith("sentinel_test_") or test_url.drivername != "postgresql+psycopg":
        raise RuntimeError("PostgreSQL tests require an explicitly named local sentinel_test_ database.")
    os.environ["DATABASE_URL"] = test_database_url
else:
    os.environ.pop("DATABASE_URL", None)

from fastapi.testclient import TestClient
from backend.main import app, LOGIN_ATTEMPTS
from backend.database import engine


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    _test_dir.cleanup()


@pytest.fixture
def client():
    LOGIN_ATTEMPTS.clear()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sign_in(client):
    def login(role="engineer"):
        LOGIN_ATTEMPTS.clear()
        r = client.post(
            "/api/auth/login",
            json={"email": f"{role}@sentinel.local", "password": "SentinelDemo!2026"},
        )
        assert r.status_code == 200, r.text
        client.headers["X-CSRF-Token"] = r.json()["csrf"]
        return r.json()["user"]

    return login
