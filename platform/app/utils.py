from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Command, Node, ResourceSnapshot

ACTIONS_NO_PARAM = {"restart_agent", "agent_status", "image_prune"}
ACTIONS_CONTAINER = {
    "container_restart",
    "container_stop",
    "container_start",
    "container_logs",
}
ACTIONS_SERVICE = {"service_restart", "service_stop", "service_status"}
ACTIONS_DEPLOY = {"project_deploy"}
ALL_ACTIONS = ACTIONS_NO_PARAM | ACTIONS_CONTAINER | ACTIONS_SERVICE | ACTIONS_DEPLOY

DEPLOY_PATH_PREFIXES = ("/opt/projects/", "/data/apps/")
MAX_CONTAINER_LOG_LINES = 1000


def normalize_deploy_path(path: str) -> str | None:
    """Unix-style whitelist path; reject traversal without OS-specific resolve."""
    raw = str(path).replace("\\", "/").strip()
    if not raw.startswith(DEPLOY_PATH_PREFIXES):
        return None
    parts = [p for p in raw.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        return None
    normalized = "/" + "/".join(parts)
    if not normalized.startswith(DEPLOY_PATH_PREFIXES):
        return None
    return normalized


def utcnow() -> datetime:
    return datetime.now(UTC)


def node_online(last_seen_at: datetime | None, now: datetime | None = None) -> bool:
    if last_seen_at is None:
        return False
    current = now or utcnow()
    if last_seen_at.tzinfo is None:
        last_seen_at = last_seen_at.replace(tzinfo=UTC)
    return (current - last_seen_at).total_seconds() < settings.online_threshold_seconds


def node_is_windows(node: Node) -> bool:
    return "windows" in (node.os or "").lower()


def latest_snapshot(db: Session, node_id: str) -> ResourceSnapshot | None:
    return (
        db.query(ResourceSnapshot)
        .filter(ResourceSnapshot.node_id == node_id)
        .order_by(ResourceSnapshot.timestamp.desc())
        .first()
    )


def _snapshot_names(snapshot: dict[str, Any] | None, key: str) -> set[str]:
    if not snapshot:
        return set()
    items = snapshot.get(key) or []
    names: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            if "name" in item:
                names.add(str(item["name"]))
            if "path" in item:
                names.add(str(item["path"]))
        elif isinstance(item, str):
            names.add(item)
    return names


def validate_command(
    db: Session,
    node: Node,
    action: str,
    params: dict[str, Any],
) -> None:
    if action not in ALL_ACTIONS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"illegal action: {action}")

    params = params or {}

    if action in ACTIONS_SERVICE and node_is_windows(node):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="service actions not supported on Windows nodes",
        )

    if action in ACTIONS_NO_PARAM:
        return

    snap_row = latest_snapshot(db, node.node_id)
    snapshot = (snap_row.snapshot if snap_row else None) or {}

    if action in ACTIONS_CONTAINER:
        name = params.get("name")
        if not name:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="params.name required")
        names = _snapshot_names(snapshot, "containers")
        if str(name) not in names:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"container not in latest snapshot: {name}",
            )
        if action == "container_logs":
            lines = int(params.get("lines") or 100)
            if lines < 1 or lines > MAX_CONTAINER_LOG_LINES:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail=f"lines must be 1..{MAX_CONTAINER_LOG_LINES}",
                )
            params["lines"] = lines
        return

    if action in ACTIONS_SERVICE:
        name = params.get("name")
        if not name:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="params.name required")
        names = _snapshot_names(snapshot, "services")
        if str(name) not in names:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"service not in latest snapshot: {name}",
            )
        return

    if action == "project_deploy":
        if not settings.project_deploy_enabled:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="project_deploy is disabled",
            )
        path = params.get("path")
        if not path or not isinstance(path, str):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="params.path required")
        normalized = normalize_deploy_path(path)
        if not normalized:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"path not in whitelist prefixes: {DEPLOY_PATH_PREFIXES}",
            )
        projects = _snapshot_names(snapshot, "projects")
        # Spec: params must exist in latest snapshot. Empty/missing snapshot => reject.
        candidates = {normalized, path, str(Path(path))}
        if not projects or not (candidates & projects):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"project path not in latest snapshot: {path}",
            )
        params["path"] = normalized
        return


def serialize_pending(command: Command) -> dict[str, Any]:
    return {
        "id": command.id,
        "action": command.action,
        "params": command.params or {},
    }


def ensure_default_admin(db: Session) -> None:
    from app.models import User
    from app.security import hash_password

    existing = db.query(User).filter(User.username == "admin").first()
    if existing:
        return
    admin = User(
        username="admin",
        password_hash=hash_password(settings.admin_password),
        must_change_password=True,
        created_at=utcnow(),
    )
    db.add(admin)
    db.commit()
