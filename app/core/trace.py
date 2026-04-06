from __future__ import annotations

import re
from contextvars import ContextVar, Token
from typing import Optional
from uuid import uuid4


TRACE_HEADER_NAME = "X-Trace-Id"
REQUEST_ID_HEADER_NAME = "X-Request-Id"
_MAX_TRACE_ID_LENGTH = 128
_TRACE_ALLOWED_PATTERN = re.compile(r"[^0-9A-Za-z._:\-]+")
_current_trace_id: ContextVar[Optional[str]] = ContextVar("current_trace_id", default=None)


def _normalize_trace_id(value: Optional[str]) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    normalized = _TRACE_ALLOWED_PATTERN.sub("-", raw)[:_MAX_TRACE_ID_LENGTH].strip("-")
    return normalized or None


def generate_trace_id() -> str:
    return uuid4().hex


def resolve_trace_id(*candidates: Optional[str]) -> str:
    for candidate in candidates:
        normalized = _normalize_trace_id(candidate)
        if normalized:
            return normalized
    return generate_trace_id()


def set_trace_id(trace_id: str) -> Token:
    return _current_trace_id.set(resolve_trace_id(trace_id))


def reset_trace_id(token: Token) -> None:
    _current_trace_id.reset(token)


def get_trace_id() -> Optional[str]:
    return _current_trace_id.get()


def compose_trace_id(child_trace_id: Optional[str]) -> str:
    parent = get_trace_id()
    child = _normalize_trace_id(child_trace_id)
    if parent and child:
        return f"{parent}:{child}"[:_MAX_TRACE_ID_LENGTH]
    if parent:
        return parent
    if child:
        return child
    return generate_trace_id()
