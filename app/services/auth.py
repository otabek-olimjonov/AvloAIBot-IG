from dataclasses import dataclass
from datetime import datetime, timedelta

import bcrypt as _bcrypt
from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def create_access_token(user_id: str, username: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": user_id, "username": username, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


@dataclass
class UserInfo:
    user_id: str | None
    username: str
    role: str


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserInfo:
    """Accepts JWT Bearer token OR X-API-Key (treated as admin for backward compat)."""
    from app.models import User

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = jwt.decode(
                token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
            )
            user_id = payload.get("sub")
            result = await db.execute(
                select(User).where(User.id == user_id, User.is_active == True)  # noqa: E712
            )
            user = result.scalar_one_or_none()
            if not user:
                raise HTTPException(status_code=401, detail="User not found or deactivated")
            return UserInfo(user_id=str(user.id), username=user.username, role=user.role)
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

    api_key = request.headers.get("X-API-Key", "")
    if api_key and api_key == settings.api_secret_key:
        return UserInfo(user_id=None, username="api_key", role="admin")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_admin(current_user: UserInfo = Depends(get_current_user)) -> UserInfo:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_user
