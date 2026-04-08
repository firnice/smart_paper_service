from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from app.core.llm_settings import load_llm_settings, load_whatai_settings
from app.core.logger import logger
from app.services.http_client import (
    HttpClientError,
    HttpNetworkError,
    HttpStatusError,
    post_json,
)


class LlmClientError(RuntimeError):
    """Base exception for LLM client failures."""


class LlmHttpError(LlmClientError):
    def __init__(self, status_code: int, body: str):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code
        self.body = body


class LlmNetworkError(LlmClientError):
    pass


def _write_call_log(
    *,
    trace_id: str,
    agent_node: Optional[str],
    provider: str,
    model: str,
    status: str,
    elapsed_ms: int,
    http_status: Optional[int] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    error_message: Optional[str] = None,
) -> None:
    """写 LLM 调用日志到 DB，失败时静默忽略，不影响主流程。"""
    try:
        from app.db.session import SessionLocal
        from app.db.models.llm_call_log import LlmCallLog

        db = SessionLocal()
        try:
            db.add(LlmCallLog(
                trace_id=trace_id,
                agent_node=agent_node,
                provider=provider,
                model=model,
                status=status,
                http_status=http_status,
                elapsed_ms=elapsed_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                error_message=error_message,
                called_at=datetime.utcnow(),
            ))
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Failed to write LlmCallLog: %s", exc)


def _extract_agent_node(trace_id: str) -> Optional[str]:
    """从 trace_id 中提取 agent_node（格式: provider:agent_node:...）。"""
    parts = trace_id.split(":")
    if len(parts) >= 2:
        return parts[1]
    return None


class BaseLlmClient:
    """Common OpenAI-compatible client — delegates IO to http_client."""

    def __init__(self, *, provider: str, base_url: str, api_key: str, timeout_seconds: int = 180):
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = max(5, int(timeout_seconds))

    def chat_completions(self, payload: dict[str, Any], *, trace_id: str) -> dict[str, Any]:
        endpoint = f"{self.base_url}/chat/completions"
        full_trace_id = f"{self.provider}:{trace_id}"
        agent_node = _extract_agent_node(full_trace_id)
        model = str(payload.get("model", ""))
        started_at = time.perf_counter()

        try:
            data = post_json(
                endpoint,
                payload,
                trace_id=full_trace_id,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout_seconds=self.timeout_seconds,
            )
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            usage = data.get("usage") or {}
            _write_call_log(
                trace_id=full_trace_id,
                agent_node=agent_node,
                provider=self.provider,
                model=model,
                status="success",
                elapsed_ms=elapsed_ms,
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
            )
            return data
        except HttpStatusError as exc:
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            _write_call_log(
                trace_id=full_trace_id,
                agent_node=agent_node,
                provider=self.provider,
                model=model,
                status="http_error",
                elapsed_ms=elapsed_ms,
                http_status=exc.status_code,
                error_message=exc.body[:500] if exc.body else None,
            )
            raise LlmHttpError(status_code=exc.status_code, body=exc.body) from exc
        except HttpNetworkError as exc:
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            _write_call_log(
                trace_id=full_trace_id,
                agent_node=agent_node,
                provider=self.provider,
                model=model,
                status="network_error",
                elapsed_ms=elapsed_ms,
                error_message=str(exc)[:500],
            )
            raise LlmNetworkError(str(exc)) from exc
        except HttpClientError as exc:
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            _write_call_log(
                trace_id=full_trace_id,
                agent_node=agent_node,
                provider=self.provider,
                model=model,
                status="client_error",
                elapsed_ms=elapsed_ms,
                error_message=str(exc)[:500],
            )
            raise LlmClientError(str(exc)) from exc


@dataclass(frozen=True)
class SiliconflowClient:
    base_client: BaseLlmClient
    default_model: Optional[str]
    ocr_model: Optional[str]


@dataclass(frozen=True)
class WhataiClient:
    base_client: BaseLlmClient
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
        diagram_svg_model=settings.diagram_svg_model,
    )
