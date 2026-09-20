import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import Log, Node, User
from app.security import safe_decode_token

router = APIRouter(tags=["ws"])


def _ws_authorized(token: str | None, db: Session) -> bool:
    if not token:
        return False
    payload = safe_decode_token(token)
    if not payload or "sub" not in payload:
        return False
    user = db.query(User).filter(User.username == payload["sub"]).first()
    return user is not None and not user.must_change_password


@router.websocket("/api/v1/nodes/{node_id}/logs")
async def ws_logs(websocket: WebSocket, node_id: str) -> None:
    token = websocket.query_params.get("token")
    # Reject before accept when possible; FastAPI still needs accept/close dance.
    await websocket.accept()
    db: Session = SessionLocal()
    try:
        if not _ws_authorized(token, db):
            await websocket.send_text(
                json.dumps({"type": "error", "detail": "unauthorized"})
            )
            await websocket.close(code=4401)
            return
        node = db.query(Node).filter(Node.node_id == node_id).first()
        if not node:
            await websocket.send_text(
                json.dumps({"type": "error", "detail": "node not found"})
            )
            await websocket.close(code=4404)
            return
    except JWTError:
        await websocket.send_text(json.dumps({"type": "error", "detail": "unauthorized"}))
        await websocket.close(code=4401)
        return
    finally:
        db.close()

    last_id = 0
    try:
        while True:
            db = SessionLocal()
            try:
                node = db.query(Node).filter(Node.node_id == node_id).first()
                if not node:
                    await websocket.send_text(
                        json.dumps({"type": "error", "detail": "node not found"})
                    )
                    break
                rows = (
                    db.query(Log)
                    .filter(Log.node_id == node_id, Log.id > last_id)
                    .order_by(Log.id.asc())
                    .limit(200)
                    .all()
                )
                if rows:
                    last_id = rows[-1].id
                    payload = [
                        {
                            "id": r.id,
                            "level": r.level,
                            "content": r.content,
                            "timestamp": r.timestamp.isoformat(),
                        }
                        for r in rows
                    ]
                    await websocket.send_text(json.dumps({"type": "logs", "items": payload}))
            finally:
                db.close()
            await asyncio.sleep(settings.ws_log_interval_seconds)
    except WebSocketDisconnect:
        return
    except Exception:
        try:
            await websocket.close()
        except Exception:
            return
