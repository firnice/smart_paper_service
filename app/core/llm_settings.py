from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
import os
from typing import Optional


DEFAULT_SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
DEFAULT_WHATAI_BASE_URL = "https://api.whatai.cc/v1"


@dataclass(frozen=True)
class LlmSettings:
    api_key: str
    base_url: str
    model: Optional[str] = None
    timeout_seconds: int = 180
    ocr_model: Optional[str] = None


@dataclass(frozen=True)
class WhataiSettings:
    api_key: str
    base_url: str
    diagram_svg_model: Optional[str] = None
    timeout_seconds: int = 180


@dataclass(frozen=True)
class BuiltinProviderSeed:
    name: str
    base_url: str
    api_key: str
    is_active: bool


def _load_from_secrets() -> dict[str, Optional[str]]:
    try:
        secrets = import_module("app.core.llm_secrets")
    except ModuleNotFoundError:
        return {}

    return {
        "api_key": getattr(secrets, "SILICONFLOW_API_KEY", None),
        "base_url": getattr(secrets, "SILICONFLOW_BASE_URL", None),
        "model": getattr(secrets, "SILICONFLOW_MODEL", None),
        "ocr_model": getattr(secrets, "SILICONFLOW_OCR_MODEL", None),
        "timeout_seconds": getattr(secrets, "SILICONFLOW_TIMEOUT_SECONDS", None),
    }


def _load_whatai_from_secrets() -> dict[str, Optional[str]]:
    try:
        secrets = import_module("app.core.llm_secrets")
    except ModuleNotFoundError:
        return {}

    return {
        "api_key": getattr(secrets, "WHATAI_API_KEY", None),
        "base_url": getattr(secrets, "WHATAI_BASE_URL", None),
        "diagram_svg_model": getattr(secrets, "WHATAI_DIAGRAM_SVG_MODEL", None),
        "timeout_seconds": getattr(secrets, "WHATAI_TIMEOUT_SECONDS", None),
    }


def load_llm_settings() -> Optional[LlmSettings]:
    config = _load_from_secrets()

    api_key = config.get("api_key") or os.getenv("SILICONFLOW_API_KEY")
    base_url = config.get("base_url") or os.getenv("SILICONFLOW_BASE_URL")
    model = config.get("model") or os.getenv("SILICONFLOW_MODEL")
    ocr_model = config.get("ocr_model") or os.getenv("SILICONFLOW_OCR_MODEL")
    timeout_value = config.get("timeout_seconds") or os.getenv("SILICONFLOW_TIMEOUT_SECONDS")

    if not api_key or not base_url:
        return None

    if not model and not ocr_model:
        return None

    timeout_seconds = 180
    if timeout_value:
        try:
            timeout_seconds = int(timeout_value)
        except ValueError:
            timeout_seconds = 180

    return LlmSettings(
        api_key=api_key,
        base_url=base_url.rstrip("/"),
        model=model,
        timeout_seconds=timeout_seconds,
        ocr_model=ocr_model,
    )


def load_whatai_settings() -> Optional[WhataiSettings]:
    config = _load_whatai_from_secrets()

    api_key = config.get("api_key") or os.getenv("WHATAI_API_KEY")
    base_url = config.get("base_url") or os.getenv("WHATAI_BASE_URL")
    diagram_svg_model = (
        config.get("diagram_svg_model")
        or os.getenv("WHATAI_DIAGRAM_SVG_MODEL")
        or "gemini-3.1-pro-preview"
    )
    timeout_value = config.get("timeout_seconds") or os.getenv("WHATAI_TIMEOUT_SECONDS")

    if not api_key or not base_url:
        return None

    if not diagram_svg_model:
        return None

    timeout_seconds = 180
    if timeout_value:
        try:
            timeout_seconds = int(timeout_value)
        except ValueError:
            timeout_seconds = 180

    return WhataiSettings(
        api_key=api_key,
        base_url=base_url.rstrip("/"),
        diagram_svg_model=diagram_svg_model,
        timeout_seconds=timeout_seconds,
    )


def load_builtin_provider_seed(provider: str) -> Optional[BuiltinProviderSeed]:
    if provider == "siliconflow":
        config = _load_from_secrets()
        api_key = str(config.get("api_key") or os.getenv("SILICONFLOW_API_KEY") or "")
        base_url = str(
            config.get("base_url")
            or os.getenv("SILICONFLOW_BASE_URL")
            or DEFAULT_SILICONFLOW_BASE_URL
        ).rstrip("/")
        return BuiltinProviderSeed(
            name="siliconflow",
            base_url=base_url,
            api_key=api_key,
            is_active=bool(api_key),
        )

    if provider == "whatai":
        config = _load_whatai_from_secrets()
        api_key = str(config.get("api_key") or os.getenv("WHATAI_API_KEY") or "")
        base_url = str(
            config.get("base_url")
            or os.getenv("WHATAI_BASE_URL")
            or DEFAULT_WHATAI_BASE_URL
        ).rstrip("/")
        return BuiltinProviderSeed(
            name="whatai",
            base_url=base_url,
            api_key=api_key,
            is_active=bool(api_key),
        )

    return None
