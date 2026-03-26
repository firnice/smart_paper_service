"""统一的下游 HTTP 客户端，所有对外请求都走这里，保证日志一致。"""

from __future__ import annotations

import http.client
import json
import re
import time
from typing import Any, Optional
from urllib import error, request

from app.core.logger import logger

_MAX_LOG_CHARS = 2800


def _truncate(value: str, max_chars: int = _MAX_LOG_CHARS) -> str:
    text = str(value or "")
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]} ...[truncated {len(text) - max_chars} chars]"


def _sanitize_for_log(payload: Any) -> Any:
    if isinstance(payload, dict):
        result: dict[str, Any] = {}
        for key, value in payload.items():
            lowered = str(key).lower()
            if lowered in {"authorization", "api_key", "apikey", "token"}:
                result[key] = "***"
            elif lowered in {"image_base64"} or (
                isinstance(value, str) and value.startswith("data:image/")
            ):
                result[key] = f"[base64 image {len(str(value))} chars]"
            else:
                result[key] = _sanitize_for_log(value)
        return result
    if isinstance(payload, list):
        return [_sanitize_for_log(item) for item in payload]
    if isinstance(payload, str):
        if payload.startswith("data:image/") and ";base64," in payload:
            prefix, _, raw = payload.partition(";base64,")
            return f"{prefix};base64,[{len(raw)} chars]"
        if re.match(r"^[A-Za-z0-9+/=]{500,}$", payload):
            return f"[base64 text {len(payload)} chars]"
        return _truncate(payload, max_chars=900)
    return payload


def _to_json_preview(payload: Any) -> str:
    try:
        encoded = json.dumps(_sanitize_for_log(payload), ensure_ascii=False)
    except Exception:
        encoded = str(payload)
    return _truncate(encoded, max_chars=_MAX_LOG_CHARS)


class HttpClientError(RuntimeError):
    """下游 HTTP 请求失败。"""


class HttpStatusError(HttpClientError):
    def __init__(self, status_code: int, body: str):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code
        self.body = body


class HttpNetworkError(HttpClientError):
    pass


def post_json(
    url: str,
    body: dict[str, Any],
    *,
    trace_id: str,
    headers: Optional[dict[str, str]] = None,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    """发送 POST JSON 请求，统一记录请求/响应/耗时日志。"""
    merged_headers = {"Content-Type": "application/json"}
    if headers:
        merged_headers.update(headers)

    logger.info(
        "HTTP_OUT request trace_id=%s url=%s body=%s",
        trace_id,
        url,
        _to_json_preview(body),
    )

    req = request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=merged_headers,
        method="POST",
    )

    started_at = time.perf_counter()
    try:
        with request.urlopen(req, timeout=max(3, timeout_seconds)) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        resp_body = exc.read().decode("utf-8", errors="replace")
        logger.error(
            "HTTP_OUT error trace_id=%s url=%s status=%s elapsed_ms=%d body=%s",
            trace_id,
            url,
            exc.code,
            elapsed_ms,
            _truncate(resp_body),
        )
        raise HttpStatusError(status_code=int(exc.code), body=resp_body) from exc
    except (TimeoutError, error.URLError, http.client.HTTPException, ConnectionError) as exc:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.warning(
            "HTTP_OUT network_error trace_id=%s url=%s elapsed_ms=%d err=%s",
            trace_id,
            url,
            elapsed_ms,
            str(exc),
        )
        raise HttpNetworkError(str(exc)) from exc

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    logger.info(
        "HTTP_OUT response trace_id=%s url=%s elapsed_ms=%d body=%s",
        trace_id,
        url,
        elapsed_ms,
        _truncate(raw),
    )

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HttpClientError(f"Invalid JSON from {url}: {str(exc)}") from exc
