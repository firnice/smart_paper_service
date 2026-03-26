from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from app.core.llm_settings import load_llm_settings, load_whatai_settings

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


class BaseLlmClient:
    """Common OpenAI-compatible client — delegates IO to http_client."""

    def __init__(self, *, provider: str, base_url: str, api_key: str, timeout_seconds: int = 180):
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = max(5, int(timeout_seconds))

    def chat_completions(self, payload: dict[str, Any], *, trace_id: str) -> dict[str, Any]:
        endpoint = f"{self.base_url}/chat/completions"
        try:
            return post_json(
                endpoint,
                payload,
                trace_id=f"{self.provider}:{trace_id}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout_seconds=self.timeout_seconds,
            )
        except HttpStatusError as exc:
            raise LlmHttpError(status_code=exc.status_code, body=exc.body) from exc
        except HttpNetworkError as exc:
            raise LlmNetworkError(str(exc)) from exc
        except HttpClientError as exc:
            raise LlmClientError(str(exc)) from exc


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
