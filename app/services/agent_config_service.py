from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Optional

from sqlalchemy.orm import Session

from app.core.llm_settings import load_llm_settings, load_whatai_settings
from app.core.logger import logger
from app.db.models.agent_config import AgentConfig
from app.services.llm_client_service import BaseLlmClient


# ---------------------------------------------------------------------------
# 默认 agent 节点定义（数据库无配置时回退使用）
# ---------------------------------------------------------------------------

AGENT_DEFAULTS: dict[str, dict] = {
    "ocr_recognize": {
        "provider": "siliconflow",
        "display_name": "OCR 试卷识别",
        "description": "调用视觉模型识别试卷中的题目",
        "model_key": "ocr_model",
        "temperature": 0.2,
        "timeout_seconds": 180,
    },
    "question_analyze": {
        "provider": "siliconflow",
        "display_name": "题目智能分析",
        "description": "分析题目推断学科、分类、错误原因",
        "model_key": "default_model",
        "temperature": 0.1,
        "timeout_seconds": 180,
    },
    "diagram_crop": {
        "provider": "whatai",
        "display_name": "图表区域裁剪",
        "description": "识别图片中的图表区域并裁剪",
        "model_key": "diagram_crop_model",
        "temperature": 0.0,
        "timeout_seconds": 180,
    },
    "diagram_svg": {
        "provider": "whatai",
        "display_name": "SVG 图表生成",
        "description": "根据题目文字生成 SVG 图表",
        "model_key": "diagram_svg_model",
        "temperature": 0.2,
        "timeout_seconds": 180,
    },
    "question_generate": {
        "provider": "siliconflow",
        "display_name": "举一反三出题",
        "description": "根据原题生成类似的练习题",
        "model_key": "default_model",
        "temperature": 0.7,
        "timeout_seconds": 180,
    },
    "trend_analyze": {
        "provider": "siliconflow",
        "display_name": "错题趋势分析",
        "description": "分析学生错题数据生成学习报告",
        "model_key": "default_model",
        "temperature": 0.3,
        "timeout_seconds": 180,
    },
}


@dataclass(frozen=True)
class ResolvedAgentConfig:
    node_name: str
    display_name: str
    description: str
    provider: str
    model: str
    fallback_models: list[str]
    base_url: str
    api_key: str
    temperature: float
    timeout_seconds: int
    max_tokens: Optional[int]
    system_prompt: Optional[str]
    user_prompt_template: Optional[str]
    is_enabled: bool
    source: str  # "database" | "default"


def normalize_model_list(models: Optional[list[str] | tuple[str, ...] | str]) -> list[str]:
    if models is None:
        return []
    if isinstance(models, str):
        candidates = [models]
    else:
        candidates = list(models)

    normalized: list[str] = []
    seen: set[str] = set()
    for raw in candidates:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def parse_fallback_models(raw_value: Optional[str]) -> list[str]:
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return normalize_model_list([part.strip() for part in raw_value.split(",")])
    if isinstance(parsed, list):
        return normalize_model_list(parsed)
    if isinstance(parsed, str):
        return normalize_model_list([parsed])
    return []


def serialize_fallback_models(models: Optional[list[str] | tuple[str, ...] | str]) -> Optional[str]:
    normalized = normalize_model_list(models)
    if not normalized:
        return None
    return json.dumps(normalized, ensure_ascii=True)


def _resolve_provider_credentials(provider: str, base_url: Optional[str], api_key_ref: Optional[str]):
    """从 provider 级别获取 base_url 和 api_key。"""
    if provider == "siliconflow":
        settings = load_llm_settings()
        if not settings:
            return None, None
        resolved_url = base_url or settings.base_url
        resolved_key = settings.api_key
        return resolved_url, resolved_key

    if provider == "whatai":
        settings = load_whatai_settings()
        if not settings:
            return None, None
        resolved_url = base_url or settings.base_url
        resolved_key = settings.api_key
        return resolved_url, resolved_key

    return base_url, None


def _resolve_default_model(provider: str, model_key: str) -> Optional[str]:
    """从 provider 环境变量中获取默认模型名。"""
    if provider == "siliconflow":
        settings = load_llm_settings()
        if not settings:
            return None
        if model_key == "ocr_model":
            return settings.ocr_model
        return settings.model

    if provider == "whatai":
        settings = load_whatai_settings()
        if not settings:
            return None
        if model_key == "diagram_crop_model":
            return settings.diagram_crop_model
        if model_key == "diagram_svg_model":
            return settings.diagram_svg_model
        return settings.diagram_crop_model

    return None


def get_agent_config(db: Optional[Session], node_name: str) -> Optional[ResolvedAgentConfig]:
    """
    获取 agent 配置。优先级:
    1. 数据库中的配置
    2. AGENT_DEFAULTS + 环境变量
    """
    # 尝试从 DB 读取
    db_config: Optional[AgentConfig] = None
    if db:
        try:
            db_config = db.query(AgentConfig).filter(AgentConfig.node_name == node_name).first()
        except Exception:
            pass

    if db_config:
        resolved_url, resolved_key = _resolve_provider_credentials(
            db_config.provider, db_config.base_url, db_config.api_key_ref
        )
        if not resolved_url or not resolved_key:
            logger.warning("Agent %s: provider %s credentials not available", node_name, db_config.provider)
            return None

        return ResolvedAgentConfig(
            node_name=node_name,
            display_name=db_config.display_name,
            description=db_config.description or "",
            provider=db_config.provider,
            model=db_config.model,
            fallback_models=parse_fallback_models(db_config.fallback_models),
            base_url=resolved_url,
            api_key=resolved_key,
            temperature=db_config.temperature if db_config.temperature is not None else 0.2,
            timeout_seconds=db_config.timeout_seconds or 180,
            max_tokens=db_config.max_tokens,
            system_prompt=db_config.system_prompt,
            user_prompt_template=db_config.user_prompt_template,
            is_enabled=db_config.is_enabled if db_config.is_enabled is not None else True,
            source="database",
        )

    # 回退到 AGENT_DEFAULTS
    defaults = AGENT_DEFAULTS.get(node_name)
    if not defaults:
        logger.warning("Unknown agent node: %s", node_name)
        return None

    provider = defaults["provider"]
    model_key = defaults.get("model_key", "default_model")
    model = _resolve_default_model(provider, model_key)
    if not model:
        logger.warning("Agent %s: no model available for provider %s", node_name, provider)
        return None

    resolved_url, resolved_key = _resolve_provider_credentials(provider, None, None)
    if not resolved_url or not resolved_key:
        logger.warning("Agent %s: provider %s credentials not available", node_name, provider)
        return None

    return ResolvedAgentConfig(
        node_name=node_name,
        display_name=defaults["display_name"],
        description=defaults.get("description", ""),
        provider=provider,
        model=model,
        fallback_models=[],
        base_url=resolved_url,
        api_key=resolved_key,
        temperature=defaults.get("temperature", 0.2),
        timeout_seconds=defaults.get("timeout_seconds", 180),
        max_tokens=None,
        system_prompt=None,
        user_prompt_template=None,
        is_enabled=True,
        source="default",
    )


def get_llm_client_for_agent(
    db: Optional[Session], node_name: str
) -> Optional[tuple[BaseLlmClient, ResolvedAgentConfig]]:
    """
    构建 BaseLlmClient + 返回完整配置。
    返回 None 表示该 agent 不可用（配置缺失或已禁用）。
    """
    config = get_agent_config(db, node_name)
    if not config:
        return None

    if not config.is_enabled:
        logger.info("Agent %s is disabled", node_name)
        return None

    client = BaseLlmClient(
        provider=config.provider,
        base_url=config.base_url,
        api_key=config.api_key,
        timeout_seconds=config.timeout_seconds,
    )
    return client, config


def list_all_agent_configs(db: Optional[Session]) -> list[ResolvedAgentConfig]:
    """列出所有 agent 节点（合并 DB + DEFAULTS）。"""
    result = []
    for node_name in AGENT_DEFAULTS:
        config = get_agent_config(db, node_name)
        if config:
            result.append(config)
        else:
            defaults = AGENT_DEFAULTS[node_name]
            result.append(ResolvedAgentConfig(
                node_name=node_name,
                display_name=defaults["display_name"],
                description=defaults.get("description", ""),
                provider=defaults["provider"],
                model="(未配置)",
                fallback_models=[],
                base_url="",
                api_key="",
                temperature=defaults.get("temperature", 0.2),
                timeout_seconds=defaults.get("timeout_seconds", 180),
                max_tokens=None,
                system_prompt=None,
                user_prompt_template=None,
                is_enabled=False,
                source="default",
            ))
    return result
