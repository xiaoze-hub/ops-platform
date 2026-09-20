"""Regression tests for review-critical security fixes."""

from fastapi.testclient import TestClient


def _reg(client: TestClient, headers, node_id="node-a", token=None, os_name="Linux"):
    tok = token or headers["Authorization"].split(" ", 1)[1]
    return client.post(
        "/api/v1/nodes/register",
        json={
            "node_id": node_id,
            "hostname": node_id,
            "ip": "1.1.1.1",
            "os": os_name,
            "agent_version": "0.2",
            "token": tok,
        },
        headers=headers,
    )


def test_register_cannot_hijack_existing_node(client: TestClient):
    h1 = {"Authorization": "Bearer token-owner"}
    assert _reg(client, h1, node_id="victim", token="token-owner").status_code == 200
    h2 = {"Authorization": "Bearer attacker-token"}
    resp = client.post(
        "/api/v1/nodes/register",
        json={
            "node_id": "victim",
            "hostname": "evil",
            "ip": "",
            "os": "Linux",
            "agent_version": "0.2",
            "token": "attacker-token",
        },
        headers=h2,
    )
    assert resp.status_code == 401
    # Owner can still heartbeat.
    hb = client.post(
        "/api/v1/nodes/victim/heartbeat",
        json={"metrics": {"cpu_percent": 1}},
        headers=h1,
    )
    assert hb.status_code == 200
    # Attacker cannot.
    hb2 = client.post(
        "/api/v1/nodes/victim/heartbeat",
        json={"metrics": {"cpu_percent": 1}},
        headers=h2,
    )
    assert hb2.status_code == 401


def test_admin_api_blocked_before_password_change(client: TestClient):
    login = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin123456"}
    )
    token = login.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    assert login.json()["must_change_password"] is True
    denied = client.get("/api/v1/nodes", headers=auth)
    assert denied.status_code == 403
    assert "password change required" in denied.json()["detail"]
    ok = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "admin123456", "new_password": "newpass12345"},
        headers=auth,
    )
    assert ok.status_code == 200
    login2 = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "newpass12345"}
    )
    auth2 = {"Authorization": f"Bearer {login2.json()['access_token']}"}
    assert client.get("/api/v1/nodes", headers=auth2).status_code == 200


def test_ws_rejects_missing_or_bad_token(client: TestClient):
    # TestClient websocket without token
    with client.websocket_connect("/api/v1/nodes/node-a/logs") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert msg["detail"] == "unauthorized"


def test_ws_accepts_admin_token_after_password_change(client: TestClient):
    login = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin123456"}
    )
    token = login.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "admin123456", "new_password": "newpass12345"},
        headers=auth,
    )
    login2 = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "newpass12345"}
    )
    admin_token = login2.json()["access_token"]
    node_headers = {"Authorization": "Bearer ws-node-token"}
    assert _reg(client, node_headers, node_id="ws-node").status_code == 200
    client.post(
        "/api/v1/nodes/ws-node/heartbeat",
        json={"logs": [{"level": "info", "content": "ws-log-line"}]},
        headers=node_headers,
    )
    with client.websocket_connect(
        f"/api/v1/nodes/ws-node/logs?token={admin_token}"
    ) as ws:
        msg = ws.receive_json()
        assert msg["type"] == "logs"
        assert any("ws-log-line" in x["content"] for x in msg["items"])


def test_project_deploy_requires_snapshot_membership(client: TestClient, monkeypatch):
    import app.utils as utils
    from app.config import get_settings

    monkeypatch.setenv("PROJECT_DEPLOY_ENABLED", "true")
    get_settings.cache_clear()
    utils.settings = get_settings()
    try:
        login = client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "admin123456"}
        )
        token = login.json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}
        client.post(
            "/api/v1/auth/change-password",
            json={"old_password": "admin123456", "new_password": "newpass12345"},
            headers=auth,
        )
        login2 = client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "newpass12345"}
        )
        auth = {"Authorization": f"Bearer {login2.json()['access_token']}"}
        node_headers = {"Authorization": "Bearer deploy-tok"}
        assert _reg(client, node_headers, node_id="deploy-node").status_code == 200
        client.post(
            "/api/v1/nodes/deploy-node/resource-snapshot",
            json={
                "snapshot": {
                    "containers": [],
                    "images": [],
                    "services": [],
                    "projects": [],
                }
            },
            headers=node_headers,
        )
        denied = client.post(
            "/api/v1/nodes/deploy-node/commands",
            json={"action": "project_deploy", "params": {"path": "/opt/projects/demo"}},
            headers=auth,
        )
        assert denied.status_code == 400
        assert "snapshot" in denied.json()["detail"]
        client.post(
            "/api/v1/nodes/deploy-node/resource-snapshot",
            json={
                "snapshot": {
                    "containers": [],
                    "images": [],
                    "services": [],
                    "projects": [{"path": "/opt/projects/demo", "name": "demo"}],
                }
            },
            headers=node_headers,
        )
        trav = client.post(
            "/api/v1/nodes/deploy-node/commands",
            json={
                "action": "project_deploy",
                "params": {"path": "/opt/projects/demo/../../etc"},
            },
            headers=auth,
        )
        assert trav.status_code == 400
        assert "whitelist" in trav.json()["detail"]
        ok = client.post(
            "/api/v1/nodes/deploy-node/commands",
            json={"action": "project_deploy", "params": {"path": "/opt/projects/demo"}},
            headers=auth,
        )
        assert ok.status_code == 200
        assert ok.json()["params"]["path"] == "/opt/projects/demo"
    finally:
        monkeypatch.setenv("PROJECT_DEPLOY_ENABLED", "false")
        get_settings.cache_clear()
        utils.settings = get_settings()


def test_pending_command_not_requeued_as_pending(client: TestClient):
    """Heartbeat dispatch marks commands running; second heartbeat has empty pending."""
    login = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin123456"}
    )
    token = login.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "admin123456", "new_password": "newpass12345"},
        headers=auth,
    )
    login2 = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "newpass12345"}
    )
    auth = {"Authorization": f"Bearer {login2.json()['access_token']}"}
    node_headers = {"Authorization": "Bearer pend-tok"}
    assert _reg(client, node_headers, node_id="pend-node").status_code == 200
    client.post(
        "/api/v1/nodes/pend-node/resource-snapshot",
        json={
            "snapshot": {
                "containers": [{"name": "web", "image": "web", "status": "Up"}],
                "images": [],
                "services": [],
                "projects": [],
            }
        },
        headers=node_headers,
    )
    cmd = client.post(
        "/api/v1/nodes/pend-node/commands",
        json={"action": "container_restart", "params": {"name": "web"}},
        headers=auth,
    ).json()
    hb1 = client.post(
        "/api/v1/nodes/pend-node/heartbeat", json={}, headers=node_headers
    ).json()
    assert len(hb1["pending_commands"]) == 1
    hb2 = client.post(
        "/api/v1/nodes/pend-node/heartbeat", json={}, headers=node_headers
    ).json()
    assert hb2["pending_commands"] == []
    cmds = client.get("/api/v1/nodes/pend-node/commands", headers=auth).json()
    assert cmds[0]["status"] == "running"
    client.post(
        f"/api/v1/nodes/pend-node/commands/{cmd['id']}/result",
        json={"status": "done", "result": "ok"},
        headers=node_headers,
    )
    cmds = client.get("/api/v1/nodes/pend-node/commands", headers=auth).json()
    assert cmds[0]["status"] == "done"
