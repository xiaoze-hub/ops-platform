from datetime import timedelta

from fastapi.testclient import TestClient


def test_register_heartbeat_snapshot_command_result_chain(
    client: TestClient, admin_token, node_headers
):
    token, headers = node_headers
    reg = {
        "node_id": "node-a",
        "hostname": "host-a",
        "ip": "10.0.0.1",
        "os": "Linux ubuntu",
        "agent_version": "0.2.0",
        "token": token,
    }
    r = client.post("/api/v1/nodes/register", json=reg, headers=headers)
    assert r.status_code == 200, r.text

    # admin_token fixture may still be must_change_password; change first if needed.
    auth_probe = client.get("/api/v1/nodes", headers={"Authorization": f"Bearer {admin_token}"})
    if auth_probe.status_code == 403:
        ch = client.post(
            "/api/v1/auth/change-password",
            json={"old_password": "admin123456", "new_password": "newpass12345"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert ch.status_code == 200
        login = client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "newpass12345"}
        )
        admin_token = login.json()["access_token"]
    auth = {"Authorization": f"Bearer {admin_token}"}

    r = client.post(
        "/api/v1/nodes/node-a/heartbeat",
        json={
            "metrics": {
                "cpu_percent": 12.5,
                "mem_percent": 40.0,
                "disk_percent": 55.0,
                "load_avg": 0.4,
            },
            "logs": [{"level": "info", "content": "hello from agent"}],
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["pending_commands"] == []

    snapshot = {
        "containers": [{"name": "nginx", "image": "nginx:alpine", "status": "Up"}],
        "images": [{"repository": "nginx", "tag": "alpine", "size": "20MB"}],
        "services": [{"name": "ssh.service", "active": "active", "description": "ssh"}],
        "projects": [{"path": "/opt/projects/demo", "name": "demo"}],
    }
    r = client.post(
        "/api/v1/nodes/node-a/resource-snapshot",
        json={"snapshot": snapshot},
        headers=headers,
    )
    assert r.status_code == 200, r.text

    r = client.get("/api/v1/nodes", headers=auth)
    assert r.status_code == 200
    nodes = r.json()
    assert len(nodes) == 1
    assert nodes[0]["node_id"] == "node-a"
    assert nodes[0]["online"] is True
    assert nodes[0]["cpu_percent"] == 12.5

    r = client.post(
        "/api/v1/nodes/node-a/commands",
        json={"action": "container_restart", "params": {"name": "nginx"}},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    cmd = r.json()
    assert cmd["status"] == "pending"

    r = client.post(
        "/api/v1/nodes/node-a/heartbeat",
        json={"metrics": {"cpu_percent": 13.0}},
        headers=headers,
    )
    assert r.status_code == 200
    pending = r.json()["pending_commands"]
    assert pending and pending[0]["action"] == "container_restart"
    assert pending[0]["params"]["name"] == "nginx"

    r = client.post(
        f"/api/v1/nodes/node-a/commands/{cmd['id']}/result",
        json={"status": "done", "result": "restarted"},
        headers=headers,
    )
    assert r.status_code == 200

    r = client.get("/api/v1/nodes/node-a/commands", headers=auth)
    assert r.status_code == 200
    items = r.json()
    assert items[0]["status"] == "done"
    assert items[0]["result"] == "restarted"

    r = client.get("/api/v1/nodes/node-a/logs", headers=auth)
    assert r.status_code == 200
    logs = r.json()
    assert any("hello from agent" in x["content"] for x in logs)

    r = client.get("/api/v1/nodes/node-a/resources", headers=auth)
    assert r.status_code == 200
    assert r.json()["snapshot"]["containers"][0]["name"] == "nginx"

    r = client.get("/api/v1/nodes/node-a/metrics?range=1h", headers=auth)
    assert r.status_code == 200
    assert len(r.json()) >= 1
    assert r.json()[0]["disk_percent"] is not None


def test_login_and_change_password(client: TestClient):
    r = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "wrong"}
    )
    assert r.status_code == 401

    r = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin123456"}
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    # Force-change enforced server-side before other admin APIs.
    assert client.get("/api/v1/nodes", headers=auth).status_code == 403

    r = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "admin123456", "new_password": "newpass12345"},
        headers=auth,
    )
    assert r.status_code == 200

    r = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "newpass12345"}
    )
    assert r.status_code == 200
    assert r.json()["must_change_password"] is False
    auth2 = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/v1/nodes", headers=auth2).status_code == 200


def test_node_token_required(client: TestClient):
    r = client.post(
        "/api/v1/nodes/register",
        json={
            "node_id": "n1",
            "hostname": "h",
            "ip": "",
            "os": "Linux",
            "agent_version": "0.2",
            "token": "tok",
        },
        headers={"Authorization": "Bearer other"},
    )
    assert r.status_code == 401


def test_online_threshold(client: TestClient, admin_token, node_headers, monkeypatch):
    token, headers = node_headers
    client.post(
        "/api/v1/nodes/register",
        json={
            "node_id": "node-old",
            "hostname": "old",
            "ip": "",
            "os": "Linux",
            "agent_version": "0.2",
            "token": token,
        },
        headers=headers,
    )
    from app.database import SessionLocal
    from app.models import Node
    from app.utils import utcnow

    db = SessionLocal()
    try:
        node = db.query(Node).filter(Node.node_id == "node-old").first()
        node.last_seen_at = utcnow() - timedelta(seconds=45)
        db.add(node)
        db.commit()
    finally:
        db.close()

    r = client.get("/api/v1/nodes", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    row = [x for x in r.json() if x["node_id"] == "node-old"][0]
    assert row["online"] is False
