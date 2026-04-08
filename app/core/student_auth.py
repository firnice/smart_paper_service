from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Header, HTTPException

from app.core.secrets_loader import secret_str

_JWT_SECRET: str = secret_str("STUDENT_JWT_SECRET", "STUDENT_JWT_SECRET") or secrets.token_hex(32)
_JWT_ALGORITHM = "HS256"
_TOKEN_EXPIRE_DAYS = int(os.getenv("STUDENT_TOKEN_EXPIRE_DAYS", "30"))


def create_student_token(student_id: int) -> str:
    """生成带 student_id 和过期时间的 JWT。"""
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": str(student_id),
        "iat": now,
        "exp": now + timedelta(days=_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def get_student_session(x_student_token: str = Header(default=None)) -> int:
    """FastAPI 依赖：校验学生 JWT，返回 student_id (int)。"""
    if not x_student_token:
        raise HTTPException(status_code=401, detail="Missing student token")
    try:
        payload = jwt.decode(x_student_token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        student_id = int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Student token expired")
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid student token")
    return student_id
