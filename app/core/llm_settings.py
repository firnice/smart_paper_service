from dataclasses import dataclass
from importlib import import_module
import os
from typing import Optional


@dataclass(frozen=True)
class LlmSettings:
    api_key: str
    base_url: str
    model: Optional[str] = None
    timeout_seconds: int = 180
    ocr_model: Optional[str] = None


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
