from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


CONFIG_PATH = Path(__file__).resolve().parent.parent / "prompt_configs" / "ocr_extract_llm.yaml"


@dataclass(frozen=True)
class OcrExtractLlmConfig:
    version: int
    provider: str
    model: str
    temperature: float
    timeout_seconds: int
    system_prompt: str
    user_prompt: str
    custom_prompt_prefix: str


def load_ocr_extract_llm_config() -> OcrExtractLlmConfig:
    with CONFIG_PATH.open("r", encoding="utf-8") as fp:
        data = yaml.safe_load(fp) or {}

    return OcrExtractLlmConfig(
        version=int(data.get("version", 1)),
        provider=str(data.get("provider") or "siliconflow").strip(),
        model=str(data.get("model") or "").strip(),
        temperature=float(data.get("temperature", 0.2)),
        timeout_seconds=int(data.get("timeout_seconds", 180)),
        system_prompt=str(data.get("system_prompt") or "").strip(),
        user_prompt=str(data.get("user_prompt") or "").strip(),
        custom_prompt_prefix=str(data.get("custom_prompt_prefix") or "").strip(),
    )
