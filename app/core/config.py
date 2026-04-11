from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_STORAGE_DIR = PROJECT_ROOT / "storage"
DEFAULT_DATABASE_URL = f"sqlite:///{(DEFAULT_STORAGE_DIR / 'smart_paper.db').as_posix()}"


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value.strip())
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value.strip())
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    value = raw_value.strip()
    return value if value else default


def _load_cors_origins() -> tuple[str, ...]:
    """优先读 llm_secrets.CORS_ORIGINS，其次环境变量，最后本地开发默认值。"""
    from app.core.secrets_loader import secret_str
    raw = secret_str("CORS_ORIGINS", "CORS_ORIGINS")
    if raw:
        return tuple(o.strip() for o in raw.split(",") if o.strip())
    return (
        "http://localhost:5173",
        "http://localhost:3000",
    )


def _load_str(secrets_attr: str, env_name: str, default: str) -> str:
    from app.core.secrets_loader import secret_str
    return secret_str(secrets_attr, env_name, default)


@dataclass(frozen=True)
class Settings:
    app_name: str = "Smart Paper Service"
    app_version: str = "0.1.0"
    environment: str = _env_str("ENVIRONMENT", "local")
    cors_origins: tuple[str, ...] = _load_cors_origins()

    # Database configuration
    database_url: str = _load_str("DATABASE_URL", "DATABASE_URL", DEFAULT_DATABASE_URL)

    # Storage configuration
    storage_base_dir: str = _load_str("STORAGE_BASE_DIR", "STORAGE_BASE_DIR", str(DEFAULT_STORAGE_DIR))
    storage_base_url: str = _load_str("STORAGE_BASE_URL", "STORAGE_BASE_URL", "http://localhost:8100/static")

    # OCR pipeline preprocessing
    enable_local_preprocess: bool = _env_bool("ENABLE_LOCAL_PREPROCESS", True)

    # Annotation cleaning fallback
    enable_annotation_saas_fallback: bool = _env_bool("ENABLE_ANNOTATION_SAAS_FALLBACK", False)
    annotation_clean_api_url: str = os.getenv("ANNOTATION_CLEAN_API_URL", "").strip()
    annotation_clean_api_key: str = os.getenv("ANNOTATION_CLEAN_API_KEY", "").strip()
    annotation_clean_timeout_seconds: int = _env_int("ANNOTATION_CLEAN_TIMEOUT_SECONDS", 20)

    # WhatAI diagram routes
    enable_whatai_diagram_svg: bool = _env_bool("ENABLE_WHATAI_DIAGRAM_SVG", True)

    # Rebuild confidence
    enable_rebuild_json: bool = _env_bool("ENABLE_REBUILD_JSON", False)
    rebuild_confidence_threshold: float = _env_float("REBUILD_CONFIDENCE_THRESHOLD", 0.80)
    force_manual_refine_on_low_conf: bool = _env_bool("FORCE_MANUAL_REFINE_ON_LOW_CONF", True)

    # Student login surface
    student_login_mode: str = _env_str("STUDENT_LOGIN_MODE", "preset")
    student_login_show_presets: bool = _env_bool("STUDENT_LOGIN_SHOW_PRESETS", True)


settings = Settings()
