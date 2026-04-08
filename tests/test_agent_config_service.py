#!/usr/bin/env python3
"""Agent config provider resolution checks."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import HTTPException  # noqa: E402

from app.api.routes.admin import update_agent  # noqa: E402
from app.core.llm_settings import BuiltinProviderSeed, LlmSettings, WhataiSettings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.models.agent_config import AgentConfig  # noqa: E402
from app.db.models.model_provider import ModelProvider  # noqa: E402
from app.schemas.admin import AgentConfigUpdate  # noqa: E402
from app.services.agent_config_service import ensure_default_model_providers, get_agent_config  # noqa: E402


def _make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def _fake_builtin_provider_seed(provider: str) -> BuiltinProviderSeed:
    if provider == "siliconflow":
        return BuiltinProviderSeed(
            name="siliconflow",
            base_url="https://db-siliconflow.example/v1",
            api_key="db-sf-key",
            is_active=True,
        )
    if provider == "whatai":
        return BuiltinProviderSeed(
            name="whatai",
            base_url="https://db-whatai.example/v1",
            api_key="db-whatai-key",
            is_active=True,
        )
    raise AssertionError(f"Unexpected provider: {provider}")


def test_builtin_model_providers_are_seeded_and_used_for_default_agent() -> None:
    db = _make_session()
    try:
        with (
            patch(
                "app.services.agent_config_service.load_builtin_provider_seed",
                side_effect=_fake_builtin_provider_seed,
            ),
            patch(
                "app.services.agent_config_service.load_llm_settings",
                return_value=LlmSettings(
                    api_key="env-sf-key",
                    base_url="https://env-siliconflow.example/v1",
                    model="deepseek-v3",
                    ocr_model="qwen-vl",
                ),
            ),
            patch(
                "app.services.agent_config_service.load_whatai_settings",
                return_value=WhataiSettings(
                    api_key="env-whatai-key",
                    base_url="https://env-whatai.example/v1",
                    diagram_svg_model="gemini-3.1-pro-preview",
                ),
            ),
        ):
            changed = ensure_default_model_providers(db)
            assert changed is True
            db.commit()

            providers = db.query(ModelProvider).order_by(ModelProvider.name).all()
            assert [provider.name for provider in providers] == ["siliconflow", "whatai"]

            config = get_agent_config(db, "question_analyze")
            assert config is not None
            assert config.provider == "siliconflow"
            assert config.base_url == "https://db-siliconflow.example/v1"
            assert config.api_key == "db-sf-key"
            assert config.model == "deepseek-v3"
    finally:
        db.close()


def test_agent_can_switch_to_provider_from_database() -> None:
    db = _make_session()
    try:
        db.add(ModelProvider(
            name="openai-compatible",
            base_url="https://openai-compatible.example/v1",
            api_key="custom-provider-key",
            is_active=True,
        ))
        db.add(AgentConfig(
            node_name="question_generate",
            display_name="举一反三出题",
            description="",
            provider="openai-compatible",
            model="gpt-4o-mini",
            temperature=0.6,
            timeout_seconds=120,
            is_enabled=True,
        ))
        db.commit()

        config = get_agent_config(db, "question_generate")
        assert config is not None
        assert config.provider == "openai-compatible"
        assert config.base_url == "https://openai-compatible.example/v1"
        assert config.api_key == "custom-provider-key"
        assert config.model == "gpt-4o-mini"
        assert config.source == "database"
    finally:
        db.close()


def test_update_agent_rejects_unknown_provider() -> None:
    db = _make_session()
    try:
        with patch(
            "app.services.agent_config_service.load_builtin_provider_seed",
            side_effect=_fake_builtin_provider_seed,
        ):
            with pytest.raises(HTTPException) as exc_info:
                update_agent(
                    node_name="question_generate",
                    payload=AgentConfigUpdate(provider="missing-provider"),
                    _="admin-session",
                    db=db,
                )

        assert exc_info.value.status_code == 400
        assert "Unknown or inactive provider" in str(exc_info.value.detail)
    finally:
        db.close()
