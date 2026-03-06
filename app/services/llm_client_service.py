from __future__ import annotations

import http.client
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional
from urllib import error, request

from app.core.llm_settings import load_llm_settings, load_whatai_settings


logger = logging.getLogger("uvicorn.error")

_MAX_LOG_CHARS = 2800


class LlmClientError(RuntimeError):
    """Base exception for LLM client failures."""


class LlmHttpError(LlmClientError):
    def __init__(self, status_code: int, body: str):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code
        self.body = body


class LlmNetworkError(LlmClientError):
    pass


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


class BaseLlmClient:
    """Common OpenAI-compatible client with baseline IO logging."""

    def __init__(self, *, provider: str, base_url: str, api_key: str, timeout_seconds: int = 180):
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = max(5, int(timeout_seconds))

    def chat_completions(self, payload: dict[str, Any], *, trace_id: str) -> dict[str, Any]:
        endpoint = f"{self.base_url}/chat/completions"
        logger.info(
            "LLM request provider=%s trace_id=%s endpoint=%s payload=%s",
            self.provider,
            trace_id,
            endpoint,
            _to_json_preview(payload),
        )

        req = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            logger.error(
                "LLM HTTP error provider=%s trace_id=%s status=%s body=%s",
                self.provider,
                trace_id,
                exc.code,
                _truncate(body),
            )
            raise LlmHttpError(status_code=int(exc.code), body=body) from exc
        except (TimeoutError, error.URLError, http.client.HTTPException, ConnectionError) as exc:
            logger.warning(
                "LLM network error provider=%s trace_id=%s err=%s",
                self.provider,
                trace_id,
                str(exc),
            )
            raise LlmNetworkError(str(exc)) from exc

        logger.info(
            "LLM response provider=%s trace_id=%s body=%s",
            self.provider,
            trace_id,
            _truncate(raw),
        )

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LlmClientError(f"Invalid JSON response from {self.provider}: {str(exc)}") from exc


@dataclass(frozen=True)
class SiliconflowClient:
    base_client: BaseLlmClient
    default_model: Optional[str]
    ocr_model: Optional[str]


@dataclass(frozen=True)
class WhataiClient:
    base_client: BaseLlmClient
    diagram_crop_model: Optional[str]
    diagram_svg_model: Optional[str]


def get_siliconflow_client() -> Optional[SiliconflowClient]:
    settings = load_llm_settings()
    if not settings:
        return None
    base = BaseLlmClient(
        provider="siliconflow",
        base_url=settings.base_url,
        api_key=settings.api_key,
        timeout_seconds=settings.timeout_seconds,
    )
    return SiliconflowClient(
        base_client=base,
        default_model=settings.model,
        ocr_model=settings.ocr_model,
    )


def get_whatai_client() -> Optional[WhataiClient]:
    settings = load_whatai_settings()
    if not settings:
        return None
    base = BaseLlmClient(
        provider="whatai",
        base_url=settings.base_url,
        api_key=settings.api_key,
        timeout_seconds=settings.timeout_seconds,
    )
    return WhataiClient(
        base_client=base,
        diagram_crop_model=settings.diagram_crop_model,
        diagram_svg_model=settings.diagram_svg_model,
    )
