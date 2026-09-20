import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))

from platform_reporter import PlatformReporter


def test_windows_service_action_rejected(monkeypatch):
    import platform as plat

    monkeypatch.setattr(plat, "system", lambda: "Windows")
    r = PlatformReporter(base_url="http://x", node_id="n", token="t")
    result = r.execute_command("service_restart", {"name": "nginx"})
    assert result["status"] == "failed"
    assert "Windows" in result["result"]


def test_illegal_action_rejected():
    r = PlatformReporter(base_url="http://x", node_id="n", token="t")
    result = r.execute_command("drop_database", {})
    assert result["status"] == "failed"
    assert "illegal action" in result["result"]


def test_project_deploy_disabled_and_prefix():
    r = PlatformReporter(base_url="http://x", node_id="n", token="t")
    assert r.execute_command("project_deploy", {"path": "/opt/projects/a"})["status"] == "failed"
    r2 = PlatformReporter(
        base_url="http://x", node_id="n", token="t", project_deploy_enabled=True
    )
    bad = r2.execute_command("project_deploy", {"path": "/etc/passwd"})
    assert bad["status"] == "failed"
    assert "whitelist" in bad["result"]


def test_collect_metrics_windows_load_avg_none(monkeypatch):
    import platform as plat

    monkeypatch.setattr(plat, "system", lambda: "Windows")
    r = PlatformReporter(base_url="http://x", node_id="n", token="t")
    metrics = r.collect_metrics()
    assert metrics["load_avg"] is None
    assert "cpu_percent" in metrics


def test_collect_resources_empty_without_docker(monkeypatch):
    import subprocess

    r = PlatformReporter(base_url="http://x", node_id="n", token="t")
    monkeypatch.setattr(
        PlatformReporter, "_run_json_lines", lambda self, args: []
    )

    def _fail_run(*args, **kwargs):
        raise FileNotFoundError("no docker/systemctl")

    monkeypatch.setattr(subprocess, "run", _fail_run)
    data = r.collect_resources()
    assert data["containers"] == []
    assert data["images"] == []
    assert data["services"] == []
    assert isinstance(data["projects"], list)


def test_agent_rejects_path_traversal_project_deploy():
    r = PlatformReporter(
        base_url="http://x", node_id="n", token="t", project_deploy_enabled=True
    )
    result = r.execute_command(
        "project_deploy", {"path": "/opt/projects/demo/../../etc"}
    )
    assert result["status"] == "failed"
    assert "whitelist" in result["result"]


def test_agent_rejects_container_not_in_snapshot():
    r = PlatformReporter(base_url="http://x", node_id="n", token="t")
    r._last_snapshot = {
        "containers": [{"name": "only-this", "image": "x", "status": "Up"}],
        "images": [],
        "services": [],
        "projects": [],
    }
    result = r.execute_command("container_restart", {"name": "other"})
    assert result["status"] == "failed"
    assert "snapshot" in result["result"]


def test_agent_fail_closed_when_snapshot_empty():
    r = PlatformReporter(base_url="http://x", node_id="n", token="t")
    r._last_snapshot = {}
    result = r.execute_command("container_restart", {"name": "web"})
    assert result["status"] == "failed"
    assert "snapshot" in result["result"]
