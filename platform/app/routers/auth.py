from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import ChangePasswordRequest, LoginRequest, Token
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> Token:
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    token = create_access_token(user.username)
    return Token(access_token=token, must_change_password=user.must_change_password)


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="old password incorrect")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    db.add(user)
    db.commit()
    return {"ok": True}
