from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Node, User
from app.security import safe_decode_token
from app.utils import latest_snapshot, serialize_pending, utcnow

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="missing token")
    payload = safe_decode_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid token")
    user = db.query(User).filter(User.username == payload["sub"]).first()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return user


def get_node_by_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Node:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="missing node token")
    node = db.query(Node).filter(Node.token == credentials.credentials).first()
    if not node:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid node token")
    return node


def get_node_or_404(node_id: str, db: Session) -> Node:
    node = db.query(Node).filter(Node.node_id == node_id).first()
    if not node:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="node not found")
    return node


__all__ = [
    "bearer_scheme",
    "get_current_user",
    "get_node_by_token",
    "get_node_or_404",
    "latest_snapshot",
    "serialize_pending",
    "utcnow",
]
