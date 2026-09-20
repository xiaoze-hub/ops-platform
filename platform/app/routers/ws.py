import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import Log, Node

router = APIRouter(tags=["ws"])


@router.websocket("/api/v1/nodes/{node_id}/logs")
async def ws_logs(websocket: WebSocket, node_id: str) -> None:
    await websocket.accept()
    last_id = 0
    try:
        while True:
            db: Session = SessionLocal()
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
