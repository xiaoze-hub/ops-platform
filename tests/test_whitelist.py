from fastapi.testclient import TestClient

from app.config import get_settings


def _auth(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


def _register(client, headers, node_id="node-a", os_name="Linux"):
    return client.post(
        "/api/v1/nodes/register",
        json={
            "node_id": node_id,
            "hostname": node_id,
            "ip": "1.1.1.1",
            "os": os_name,
            "agent_version": "0.2",
            "token": headers["Authorization"].split(" ", 1)[1],
        },
        headers=headers,
    )


def _snapshot(client, headers, node_id="node-a"):
    return client.post(
        f"/api/v1/nodes/{node_id}/resource-snapshot",
        json={
            "snapshot": {
                "containers": [{"name": "web", "image": "web:1", "status": "Up"}],
                "images": [],
                "services": [{"name": "nginx.service", "active": "active", "description": ""}],
                "projects": [{"path": "/opt/projects/demo", "name": "demo"}],
            }
        },
        headers=headers,
    )


def test_illegal_action_rejected(client: TestClient, admin_token, node_headers):
    _, headers = node_headers
    _register(client, headers)
    _snapshot(client, headers)
    r = client.post(
        "/api/v1/nodes/node-a/commands",
        json={"action": "rm_rf_everything", "params": {}},
        headers=_auth(admin_token),
    )
    assert r.status_code == 400
    assert "illegal action" in r.json()["detail"]


def test_container_name_must_exist_in_snapshot(client: TestClient, admin_token, node_headers):
    _, headers = node_headers
    _register(client, headers)
    _snapshot(client, headers)
    r = client.post(
        "/api/v1/nodes/node-a/commands",
        json={"action": "container_restart", "params": {"name": "not-exist"}},
        headers=_auth(admin_token),
    )
    assert r.status_code == 400
    assert "snapshot" in r.json()["detail"]


def test_windows_service_rejected(client: TestClient, admin_token, node_headers):
    _, headers = node_headers
    _register(client, headers, node_id="node-win", os_name="Windows 11")
    _snapshot(client, headers, node_id="node-win")
    r = client.post(
        "/api/v1/nodes/node-win/commands",
        json={"action": "service_restart", "params": {"name": "nginx.service"}},
        headers=_auth(admin_token),
    )
    assert r.status_code == 400
    assert "Windows" in r.json()["detail"]


def test_project_deploy_disabled_by_default(client: TestClient, admin_token, node_headers):
    _, headers = node_headers
    _register(client, headers)
    _snapshot(client, headers)
    settings = get_settings()
    assert settings.project_deploy_enabled is False
    r = client.post(
        "/api/v1/nodes/node-a/commands",
        json={"action": "project_deploy", "params": {"path": "/opt/projects/demo"}},
        headers=_auth(admin_token),
    )
    assert r.status_code == 400
    assert "disabled" in r.json()["detail"]


def test_container_logs_lines_limit(client: TestClient, admin_token, node_headers):
    _, headers = node_headers
    _register(client, headers)
    _snapshot(client, headers)
    r = client.post(
        "/api/v1/nodes/node-a/commands",
        json={"action": "container_logs", "params": {"name": "web", "lines": 5000}},
        headers=_auth(admin_token),
    )
    assert r.status_code == 400


def test_retention_cleanup(client: TestClient, node_headers):
    from datetime import timedelta

    from app.database import SessionLocal
    from app.models import Log, Metric
    from app.retention import cleanup_expired
    from app.utils import utcnow

    _, headers = node_headers
    _register(client, headers)
    db = SessionLocal()
    try:
        now = utcnow()
        db.add(
            Metric(
                node_id="node-a",
                cpu_percent=1,
                mem_percent=1,
                disk_percent=1,
                load_avg=0,
                timestamp=now - timedelta(days=10),
            )
        )
        db.add(
            Log(
                node_id="node-a",
                level="info",
                content="old log",
                timestamp=now - timedelta(days=5),
            )
        )
        db.add(
            Metric(
                node_id="node-a",
                cpu_percent=2,
                mem_percent=2,
                disk_percent=2,
                load_avg=0,
                timestamp=now,
            )
        )
        db.add(Log(node_id="node-a", level="info", content="new log", timestamp=now))
        db.commit()
        result = cleanup_expired(db)
        assert result["metrics_deleted"] == 1
        assert result["logs_deleted"] == 1
        assert db.query(Metric).count() == 1
        assert db.query(Log).count() == 1
    finally:
        db.close()
