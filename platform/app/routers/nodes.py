from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import (
    bearer_scheme,
    get_node_by_token,
    get_node_or_404,
    require_password_changed,
    utcnow,
)
from app.models import Command, Log, Metric, Node, ResourceSnapshot
from app.schemas import (
    CommandCreate,
    CommandOut,
    HeartbeatIn,
    HeartbeatOut,
    LogOut,
    MetricOut,
    NodeDetailOut,
    NodeOut,
    NodeRegister,
    PendingCommand,
)
from app.utils import latest_snapshot, node_online, serialize_pending, validate_command

router = APIRouter(prefix="/api/v1/nodes", tags=["nodes"])


def _node_out(node: Node, latest: Metric | None = None) -> NodeOut:
    return NodeOut(
        node_id=node.node_id,
        hostname=node.hostname,
        ip=node.ip,
        os=node.os,
        agent_version=node.agent_version,
        status=node.status,
        online=node_online(node.last_seen_at),
        last_seen_at=node.last_seen_at,
        created_at=node.created_at,
        cpu_percent=latest.cpu_percent if latest else None,
        mem_percent=latest.mem_percent if latest else None,
        disk_percent=latest.disk_percent if latest else None,
        load_avg=latest.load_avg if latest else None,
    )


def _latest_metric(db: Session, node_id: str) -> Metric | None:
    return (
        db.query(Metric)
        .filter(Metric.node_id == node_id)
        .order_by(Metric.timestamp.desc())
        .first()
    )


@router.post("/register")
def register_node(
    body: NodeRegister,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="missing node token")
    presented = credentials.credentials
    node = db.query(Node).filter(Node.node_id == body.node_id).first()
    now = utcnow()
    if node:
        # Existing node: must prove CURRENT token. Never accept a stranger's bearer.
        if presented != node.token:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid node token")
        # Optional rotation: body.token may replace token only after proving old one.
        if body.token and body.token != node.token:
            conflict = db.query(Node).filter(Node.token == body.token).first()
            if conflict and conflict.node_id != node.node_id:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="token already used")
            node.token = body.token
    else:
        # First registration: bearer must equal the pre-shared token being claimed.
        if presented != body.token:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="bearer must match node token")
        conflict = db.query(Node).filter(Node.token == body.token).first()
        if conflict:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="token already used")
        node = Node(node_id=body.node_id, token=body.token, created_at=now)
    node.hostname = body.hostname
    node.ip = body.ip
    node.os = body.os
    node.agent_version = body.agent_version
    node.last_seen_at = now
    node.status = "online"
    db.add(node)
    db.commit()
    return {"ok": True, "node_id": node.node_id}


@router.post("/{node_id}/heartbeat", response_model=HeartbeatOut)
def heartbeat(
    node_id: str,
    body: HeartbeatIn,
    db: Session = Depends(get_db),
    node: Node = Depends(get_node_by_token),
) -> HeartbeatOut:
    if node.node_id != node_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="node_id mismatch")
    now = utcnow()
    node.last_seen_at = now
    node.status = "online"

    if body.metrics:
        db.add(
            Metric(
                node_id=node_id,
                cpu_percent=body.metrics.cpu_percent,
                mem_percent=body.metrics.mem_percent,
                disk_percent=body.metrics.disk_percent,
                load_avg=body.metrics.load_avg,
                timestamp=now,
            )
        )

    for item in body.logs or []:
        level = str(item.get("level", "info")).lower()
        if level not in {"info", "warn", "error"}:
            level = "info"
        db.add(
            Log(
                node_id=node_id,
                level=level,
                content=str(item.get("content", "")),
                timestamp=now,
            )
        )

    for item in body.command_results or []:
        try:
            cmd_id = int(item.get("id", 0))
        except (TypeError, ValueError):
            continue
        cmd = (
            db.query(Command)
            .filter(Command.id == cmd_id, Command.node_id == node_id)
            .first()
        )
        if not cmd:
            continue
        st = str(item.get("status", "done"))
        cmd.status = st if st in {"done", "failed"} else "failed"
        cmd.result = str(item.get("result", ""))
        cmd.finished_at = now

    pending = (
        db.query(Command)
        .filter(Command.node_id == node_id, Command.status == "pending")
        .order_by(Command.id.asc())
        .all()
    )
    # Dispatch once: move to running so failed result-reporting cannot re-flood agents.
    for cmd in pending:
        cmd.status = "running"
        db.add(cmd)
    db.add(node)
    db.commit()
    return HeartbeatOut(
        pending_commands=[PendingCommand(**serialize_pending(c)) for c in pending]
    )


@router.post("/{node_id}/resource-snapshot")
def resource_snapshot(
    node_id: str,
    snapshot: dict[str, Any],
    db: Session = Depends(get_db),
    node: Node = Depends(get_node_by_token),
) -> dict:
    if node.node_id != node_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="node_id mismatch")
    payload = snapshot.get("snapshot", snapshot)
    now = utcnow()
    db.add(ResourceSnapshot(node_id=node_id, snapshot=payload, timestamp=now))
    node.last_seen_at = now
    node.status = "online"
    db.add(node)
    db.commit()
    return {"ok": True}


@router.get("", response_model=list[NodeOut])
def list_nodes(
    db: Session = Depends(get_db),
    _user=Depends(require_password_changed),
) -> list[NodeOut]:
    nodes = db.query(Node).order_by(Node.node_id.asc()).all()
    return [_node_out(n, _latest_metric(db, n.node_id)) for n in nodes]


@router.get("/{node_id}", response_model=NodeDetailOut)
def node_detail(
    node_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_password_changed),
) -> NodeDetailOut:
    node = get_node_or_404(node_id, db)
    out = _node_out(node, _latest_metric(db, node_id))
    return NodeDetailOut(**out.model_dump())


@router.get("/{node_id}/resources")
def node_resources(
    node_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_password_changed),
) -> dict:
    get_node_or_404(node_id, db)
    snap = latest_snapshot(db, node_id)
    return {
        "node_id": node_id,
        "snapshot": snap.snapshot if snap else {},
        "timestamp": snap.timestamp if snap else None,
    }


@router.get("/{node_id}/metrics", response_model=list[MetricOut])
def node_metrics(
    node_id: str,
    range: str = Query("1h", pattern="^(1h|6h|24h)$"),
    db: Session = Depends(get_db),
    _user=Depends(require_password_changed),
) -> list[MetricOut]:
    get_node_or_404(node_id, db)
    hours = {"1h": 1, "6h": 6, "24h": 24}[range]
    cutoff = utcnow() - timedelta(hours=hours)
    rows = (
        db.query(Metric)
        .filter(Metric.node_id == node_id, Metric.timestamp >= cutoff)
        .order_by(Metric.timestamp.asc())
        .all()
    )
    return [MetricOut.model_validate(r) for r in rows]


@router.get("/{node_id}/logs", response_model=list[LogOut])
def node_logs(
    node_id: str,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _user=Depends(require_password_changed),
) -> list[LogOut]:
    get_node_or_404(node_id, db)
    rows = (
        db.query(Log)
        .filter(Log.node_id == node_id)
        .order_by(Log.id.desc())
        .limit(limit)
        .all()
    )
    return [LogOut.model_validate(r) for r in reversed(rows)]


@router.post("/{node_id}/commands", response_model=CommandOut)
def create_command(
    node_id: str,
    body: CommandCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_password_changed),
) -> CommandOut:
    node = get_node_or_404(node_id, db)
    params = body.params or {}
    validate_command(db, node, body.action, params)
    cmd = Command(
        node_id=node_id,
        action=body.action,
        params=params,
        status="pending",
        created_at=utcnow(),
    )
    db.add(cmd)
    db.commit()
    db.refresh(cmd)
    return CommandOut.model_validate(cmd)


@router.get("/{node_id}/commands", response_model=list[CommandOut])
def list_commands(
    node_id: str,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _user=Depends(require_password_changed),
) -> list[CommandOut]:
    get_node_or_404(node_id, db)
    rows = (
        db.query(Command)
        .filter(Command.node_id == node_id)
        .order_by(Command.id.desc())
        .limit(limit)
        .all()
    )
    return [CommandOut.model_validate(r) for r in rows]


@router.post("/{node_id}/commands/{command_id}/result")
def command_result(
    node_id: str,
    command_id: int,
    body: dict[str, Any],
    db: Session = Depends(get_db),
    node: Node = Depends(get_node_by_token),
) -> dict:
    if node.node_id != node_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="node_id mismatch")
    cmd = (
        db.query(Command)
        .filter(Command.id == command_id, Command.node_id == node_id)
        .first()
    )
    if not cmd:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="command not found")
    st = str(body.get("status", "failed"))
    cmd.status = st if st in {"done", "failed"} else "failed"
    cmd.result = str(body.get("result", ""))
    cmd.finished_at = utcnow()
    db.add(cmd)
    db.commit()
    return {"ok": True}
