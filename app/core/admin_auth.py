from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Header, HTTPException

from app.core.secrets_loader import secret_str

# Secret key for signing JWTs — llm_secrets > env > random（重启后旧 token 失效）
_JWT_SECRET: str = secret_str("ADMIN_JWT_SECRET", "ADMIN_JWT_SECRET") or secrets.token_hex(32)
_JWT_ALGORITHM = "HS256"
_TOKEN_EXPIRE_HOURS = int(os.getenv("ADMIN_TOKEN_EXPIRE_HOURS", "8"))


def load_admin_credentials() -> tuple[str, str]:
    """从 llm_secrets 或环境变量加载管理员账号密码。"""
    username = secret_str("ADMIN_USERNAME", "ADMIN_USERNAME")
    password = secret_str("ADMIN_PASSWORD", "ADMIN_PASSWORD")
    return username, password


def create_admin_token() -> str:
    """生成带过期时间的 JWT admin token。"""
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": "admin",
        "iat": now,
        "exp": now + timedelta(hours=_TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def get_admin_session(x_admin_token: str = Header(default=None)) -> str:
    if not x_admin_token:
        raise HTTPException(status_code=401, detail="Missing admin token")
    try:
        payload = jwt.decode(x_admin_token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        if payload.get("sub") != "admin":
            raise HTTPException(status_code=401, detail="Invalid admin token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Admin token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return x_admin_token
