import os
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


os.environ.setdefault("APP_SECRET", "test-secret-key")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/test_tetra_host.db")
os.environ.setdefault("ALLOWED_HOSTS_RAW", "127.0.0.1,localhost,testserver")
os.environ.setdefault("ADMIN_BOOTSTRAP_EMAIL", "admin@example.com")
os.environ.setdefault("ADMIN_BOOTSTRAP_PASSWORD", "supersecurepassword")
os.environ.setdefault("ADMIN_BOOTSTRAP_NAME", "Test Admin")

TEST_DB_PATH = Path("data/test_tetra_host.db")

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.main import app  # noqa: E402


def extract_csrf_token(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


@pytest.fixture(autouse=True)
def _isolate_test_db():
    """Give every test (not only those using ``client``) a fresh DB file, so direct-DB
    tests (``session_scope``) can't leak rows — e.g. a seeded plan — into later tests/runs."""
    Path("data").mkdir(exist_ok=True)
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    yield
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def authenticated_client(client: TestClient) -> TestClient:
    login_page = client.get("/auth/login")
    csrf_token = extract_csrf_token(login_page.text)
    response = client.post(
        "/auth/login",
        data={
            "email": os.environ["ADMIN_BOOTSTRAP_EMAIL"],
            "password": os.environ["ADMIN_BOOTSTRAP_PASSWORD"],
            "csrf_token": csrf_token,
            "next_url": "/dashboard",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client
