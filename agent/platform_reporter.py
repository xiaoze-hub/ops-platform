"""Ops platform agent reporter — minimal invasion, daemon thread, never kill host."""

from __future__ import annotations

import platform as _platform
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import psutil

WHITELIST_ACTIONS = {
    "restart_agent",
    "agent_status",
    "container_restart",
    "container_stop",
    "container_start",
    "container_logs",
    "service_restart",
    "service_stop",
    "service_status",
    "image_prune",
    "project_deploy",
}
SERVICE_ACTIONS = {"service_restart", "service_stop", "service_status"}
DEPLOY_PATH_PREFIXES = ("/opt/projects/", "/data/apps/")
MAX_CONTAINER_LOG_LINES = 1000
HEARTBEAT_INTERVAL = 10
SNAPSHOT_INTERVAL = 60
HTTP_TIMEOUT = 25


class PlatformReporter:
    def __init__(
        self,
        base_url: str,
        node_id: str,
        token: str,
        agent_version: str = "0.2.0",
        project_deploy_enabled: bool = False,
        hostname: str | None = None,
        ip: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.node_id = node_id
        self.token = token
        self.agent_version = agent_version
        self.project_deploy_enabled = project_deploy_enabled
        self.hostname = hostname or _platform.node() or "unknown"
        self.ip = ip
        self.os_name = f"{_platform.system()} {_platform.release()}"
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._registered = False
        self._last_snapshot_at = 0.0
        self._on_restart_agent: Any = None

    def set_restart_agent_handler(self, handler) -> None:
        self._on_restart_agent = handler

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def _safe_post(self, path: str, json_body: dict[str, Any]) -> dict[str, Any] | None:
        url = f"{self.base_url}{path}"
        try:
            resp = httpx.post(
                url, json=json_body, headers=self._headers(), timeout=HTTP_TIMEOUT
            )
            if resp.status_code >= 400:
                return None
            return resp.json()
        except Exception:
            return None

    def collect_metrics(self) -> dict[str, Any]:
        load_avg: float | None
        if _platform.system() == "Windows":
            load_avg = None
        else:
            try:
                load_avg = float(psutil.getloadavg()[0])
            except Exception:
                load_avg = None
        try:
            disk = psutil.disk_usage("/").percent
        except Exception:
            try:
                disk = psutil.disk_usage("C:\\").percent
            except Exception:
                disk = None
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "mem_percent": psutil.virtual_memory().percent,
            "disk_percent": disk,
            "load_avg": load_avg,
        }

    def _run_json_lines(self, args: list[str]) -> list[dict[str, Any]]:
        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=15,
                shell=False,
                check=False,
            )
        except Exception:
            return []
        if proc.returncode != 0:
            return []
        items: list[dict[str, Any]] = []
        for line in (proc.stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
            import json

            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                items.append(obj)
        return items

    def collect_resources(self) -> dict[str, Any]:
        containers_raw = self._run_json_lines(["docker", "ps", "-a", "--format", "{{json .}}"])
        containers = []
        for item in containers_raw:
            containers.append(
                {
                    "name": item.get("Names") or item.get("Name") or "",
                    "image": item.get("Image", ""),
                    "status": item.get("Status", ""),
                }
            )
        images_raw = self._run_json_lines(["docker", "images", "--format", "{{json .}}"])
        images = []
        for item in images_raw:
            images.append(
                {
                    "repository": item.get("Repository", ""),
                    "tag": item.get("Tag", ""),
                    "size": item.get("Size", ""),
                }
            )
        services: list[dict[str, str]] = []
        if _platform.system() != "Windows":
            try:
                proc = subprocess.run(
                    ["systemctl", "list-units", "--type=service", "--no-pager", "--no-legend"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    shell=False,
                    check=False,
                )
                if proc.returncode == 0:
                    for line in (proc.stdout or "").splitlines():
                        parts = line.split()
                        if len(parts) >= 4:
                            services.append(
                                {
                                    "name": parts[0],
                                    "active": parts[2],
                                    "description": " ".join(parts[4:]) if len(parts) > 4 else "",
                                }
                            )
            except Exception:
                services = []
        projects: list[dict[str, str]] = []
        for prefix in DEPLOY_PATH_PREFIXES:
            root = Path(prefix)
            if not root.is_dir():
                continue
            try:
                for child in root.iterdir():
                    if child.is_dir():
                        projects.append({"path": str(child), "name": child.name})
            except Exception:
                continue
        return {
            "containers": containers,
            "images": images,
            "services": services,
            "projects": projects,
        }

    def get_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        # Host agent may override later; default returns empty recent log sample.
        return []

    def register(self) -> bool:
        body = {
            "node_id": self.node_id,
            "hostname": self.hostname,
            "ip": self.ip,
            "os": self.os_name,
            "agent_version": self.agent_version,
            "token": self.token,
        }
        result = self._safe_post("/api/v1/nodes/register", body)
        self._registered = bool(result and result.get("ok"))
        return self._registered

    def send_heartbeat(self) -> list[dict[str, Any]]:
        metrics = self.collect_metrics()
        logs = self.get_logs(limit=50)
        body = {"metrics": metrics, "logs": logs, "command_results": []}
        result = self._safe_post(f"/api/v1/nodes/{self.node_id}/heartbeat", body)
        if not result:
            return []
        return list(result.get("pending_commands") or [])

    def send_snapshot(self) -> None:
        snapshot = self.collect_resources()
        self._safe_post(
            f"/api/v1/nodes/{self.node_id}/resource-snapshot",
            {"snapshot": snapshot},
        )
        self._last_snapshot_at = time.time()

    def execute_command(self, action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = dict(params or {})
        if action not in WHITELIST_ACTIONS:
            return {"status": "failed", "result": f"illegal action: {action}"}
        if action in SERVICE_ACTIONS and _platform.system() == "Windows":
            return {"status": "failed", "result": "service actions not supported on Windows"}
        try:
            if action == "agent_status":
                return {"status": "done", "result": "agent running"}
            if action == "restart_agent":
                if self._on_restart_agent:
                    self._on_restart_agent()
                return {"status": "done", "result": "restart scheduled"}
            if action.startswith("container_"):
                name = str(params.get("name") or "")
                if not name:
                    return {"status": "failed", "result": "params.name required"}
                if action == "container_logs":
                    lines = int(params.get("lines") or 100)
                    lines = max(1, min(lines, MAX_CONTAINER_LOG_LINES))
                    return self._run_cmd(["docker", "logs", "--tail", str(lines), name])
                verb = {
                    "container_restart": "restart",
                    "container_stop": "stop",
                    "container_start": "start",
                }[action]
                return self._run_cmd(["docker", verb, name])
            if action in SERVICE_ACTIONS:
                name = str(params.get("name") or "")
                if not name:
                    return {"status": "failed", "result": "params.name required"}
                verb = {
                    "service_restart": "restart",
                    "service_stop": "stop",
                    "service_status": "status",
                }[action]
                return self._run_cmd(["systemctl", verb, name])
            if action == "image_prune":
                return self._run_cmd(["docker", "image", "prune", "-f"])
            if action == "project_deploy":
                if not self.project_deploy_enabled:
                    return {"status": "failed", "result": "project_deploy is disabled"}
                path = str(params.get("path") or "")
                if not path.startswith(DEPLOY_PATH_PREFIXES):
                    return {"status": "failed", "result": "path not in whitelist"}
                deploy_sh = Path(path) / "deploy.sh"
                if not deploy_sh.is_file():
                    return {"status": "failed", "result": "deploy.sh not found"}
                return self._run_cmd(["bash", str(deploy_sh)], cwd=path)
        except Exception as exc:
            return {"status": "failed", "result": str(exc)}
        return {"status": "failed", "result": f"unhandled action: {action}"}

    def _run_cmd(self, args: list[str], cwd: str | None = None) -> dict[str, Any]:
        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=60,
                shell=False,
                check=False,
                cwd=cwd,
            )
        except Exception as exc:
            return {"status": "failed", "result": str(exc)}
        out = (proc.stdout or "") + (proc.stderr or "")
        status = "done" if proc.returncode == 0 else "failed"
        return {"status": status, "result": out[-4000:]}

    def _report_result(self, command_id: int, result: dict[str, Any]) -> None:
        self._safe_post(
            f"/api/v1/nodes/{self.node_id}/commands/{command_id}/result",
            {"status": result.get("status", "failed"), "result": str(result.get("result", ""))},
        )

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                if not self._registered:
                    self.register()
                pending = self.send_heartbeat()
                for cmd in pending:
                    result = self.execute_command(cmd.get("action", ""), cmd.get("params") or {})
                    self._report_result(int(cmd.get("id", 0)), result)
                now = time.time()
                if now - self._last_snapshot_at >= SNAPSHOT_INTERVAL:
                    self.send_snapshot()
            except Exception:
                # Never kill the host process.
                pass
            self._stop.wait(HEARTBEAT_INTERVAL)

    def start_reporting(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="ops-platform-reporter", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)


def start_reporting(base_url: str, node_id: str, token: str, **kwargs) -> PlatformReporter:
    reporter = PlatformReporter(base_url=base_url, node_id=node_id, token=token, **kwargs)
    reporter.start_reporting()
    return reporter


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()
