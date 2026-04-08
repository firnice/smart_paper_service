"""从 llm_secrets.py 或环境变量加载配置，llm_secrets 优先。"""
from __future__ import annotations

import os
from importlib import import_module
from typing import Any


def _secrets() -> Any:
    try:
        return import_module("app.core.llm_secrets")
    except ModuleNotFoundError:
        return None


def secret_str(attr: str, env_name: str, default: str = "") -> str:
    """读取字符串配置：llm_secrets.attr → 环境变量 env_name → default。"""
    mod = _secrets()
    if mod is not None:
        val = getattr(mod, attr, None)
        if isinstance(val, str) and val.strip():
            return val.strip()
    env_val = os.getenv(env_name, "").strip()
    return env_val if env_val else default
