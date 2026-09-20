import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_ENV = {
    "DB_HOST": os.environ.get("TEST_DB_HOST", "127.0.0.1"),
    "DB_PORT": os.environ.get("TEST_DB_PORT", "5433"),
    "DB_USER": "ops",
    "DB_PASSWORD": "ops_test_password",
    "DB_NAME": "ops_platform_test",
    "SECRET_KEY": "test-secret-key",
    "ADMIN_PASSWORD": "admin123456",
    "PROJECT_DEPLOY_ENABLED": "false",
    "METRICS_RETENTION_DAYS": "7",
    "LOGS_RETENTION_DAYS": "3",
}
os.environ.update(TEST_ENV)

ROOT = Path(__file__).resolve().parents[1]
PLATFORM = ROOT / "platform"
AGENT = ROOT / "agent"
for path in (PLATFORM, AGENT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

for mod_name in list(sys.modules):
    if mod_name == "app" or mod_name.startswith("app."):
        del sys.modules[mod_name]

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    os.environ["PROJECT_DEPLOY_ENABLED"] = "false"
    import app.utils as utils
    from app.config import get_settings

    get_settings.cache_clear()
    utils.settings = get_settings()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def admin_token(client: TestClient) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin123456"}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["must_change_password"] is True
    token = data["access_token"]
    ch = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "admin123456", "new_password": "newpass12345"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ch.status_code == 200
    login2 = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "newpass12345"}
    )
    assert login2.status_code == 200
    assert login2.json()["must_change_password"] is False
    return login2.json()["access_token"]


@pytest.fixture()
def node_headers():
    token = "node-token-001"
    return token, {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def registered_node(client: TestClient, node_headers):
    token, headers = node_headers
    body = {
        "node_id": "node-a",
        "hostname": "host-a",
        "ip": "10.0.0.1",
        "os": "Linux",
        "agent_version": "0.2.0",
        "token": token,
    }
    resp = client.post("/api/v1/nodes/register", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    return body
