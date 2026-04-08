import json
import time
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.admin_auth import get_admin_session
from app.db.models.agent_config import AgentConfig
from app.db.models.llm_call_log import LlmCallLog
from app.db.models.model_provider import ModelProvider
from app.db.session import get_db
from app.schemas.admin import (
    AgentConfigResponse,
    AgentConfigUpdate,
    AgentTestRequest,
    AgentTestResponse,
    LlmCallLogResponse,
    LlmLogListResponse,
    LlmStatsAgentBreakdown,
    LlmStatsOverviewResponse,
    ModelProviderCreate,
    ModelProviderResponse,
    ModelProviderUpdate,
)
from app.services.agent_config_service import (
    AGENT_DEFAULTS,
    BUILTIN_PROVIDER_NAMES,
    ensure_default_model_providers,
    get_agent_config,
    get_model_provider_by_name,
    get_llm_client_for_agent,
    list_all_agent_configs,
    normalize_model_list,
    parse_fallback_models,
    serialize_fallback_models,
)

router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _config_to_response(config) -> AgentConfigResponse:
    return AgentConfigResponse(
        node_name=config.node_name,
        display_name=config.display_name,
        description=config.description,
        provider=config.provider,
        model=config.model,
        fallback_models=list(config.fallback_models),
        temperature=config.temperature,
        timeout_seconds=config.timeout_seconds,
        max_tokens=config.max_tokens,
        system_prompt=config.system_prompt,
        user_prompt_template=config.user_prompt_template,
        is_enabled=config.is_enabled,
        source=config.source,
    )


def _parse_provider_models(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(m) for m in parsed if str(m).strip()]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def _provider_to_response(p: ModelProvider) -> ModelProviderResponse:
    key = p.api_key or ""
    masked = ("***" + key[-4:]) if len(key) >= 4 else "***"
    return ModelProviderResponse(
        id=p.id,
        name=p.name,
        base_url=p.base_url,
        api_key_masked=masked,
        is_active=p.is_active,
        models=_parse_provider_models(p.models),
        created_at=p.created_at,
    )


# ── Agent config routes ───────────────────────────────────────────────────────

@router.get("/api/admin/agents", response_model=List[AgentConfigResponse])
def list_agents(_: str = Depends(get_admin_session), db: Session = Depends(get_db)):
    if ensure_default_model_providers(db):
        db.commit()
    configs = list_all_agent_configs(db)
    return [_config_to_response(c) for c in configs]


@router.get("/api/admin/agents/{node_name}", response_model=AgentConfigResponse)
def get_agent(node_name: str, _: str = Depends(get_admin_session), db: Session = Depends(get_db)):
    if ensure_default_model_providers(db):
        db.commit()
    config = get_agent_config(db, node_name)
    if not config:
        if node_name not in AGENT_DEFAULTS:
            raise HTTPException(status_code=404, detail=f"Unknown agent: {node_name}")
        defaults = AGENT_DEFAULTS[node_name]
        return AgentConfigResponse(
            node_name=node_name,
            display_name=defaults["display_name"],
            description=defaults.get("description", ""),
            provider=defaults["provider"],
            model="(未配置)",
            fallback_models=[],
            temperature=defaults.get("temperature", 0.2),
            timeout_seconds=defaults.get("timeout_seconds", 180),
            max_tokens=None,
            system_prompt=None,
            user_prompt_template=None,
            is_enabled=False,
            source="default",
        )
    return _config_to_response(config)


@router.put("/api/admin/agents/{node_name}", response_model=AgentConfigResponse)
def update_agent(node_name: str, payload: AgentConfigUpdate, _: str = Depends(get_admin_session), db: Session = Depends(get_db)):
    if node_name not in AGENT_DEFAULTS:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {node_name}")
    ensure_default_model_providers(db)

    row = db.query(AgentConfig).filter(AgentConfig.node_name == node_name).first()
    defaults = AGENT_DEFAULTS[node_name]

    if not row:
        current_config = get_agent_config(db, node_name)
        row = AgentConfig(
            node_name=node_name,
            display_name=defaults["display_name"],
            description=defaults.get("description", ""),
            provider=defaults["provider"],
            model=current_config.model if current_config else "(未配置)",
            temperature=defaults.get("temperature", 0.2),
            timeout_seconds=defaults.get("timeout_seconds", 180),
            is_enabled=True,
        )
        db.add(row)

    if payload.display_name is not None:
        row.display_name = payload.display_name
    if payload.description is not None:
        row.description = payload.description
    if payload.provider is not None:
        provider_row = get_model_provider_by_name(db, payload.provider)
        if not provider_row or not provider_row.is_active:
            raise HTTPException(status_code=400, detail=f"Unknown or inactive provider: {payload.provider}")
        row.provider = payload.provider
    existing_fallback_models = parse_fallback_models(row.fallback_models)
    if payload.model is not None:
        previous_model = row.model
        row.model = payload.model
        fallback_models = (
            normalize_model_list(payload.fallback_models)
            if payload.fallback_models is not None
            else list(existing_fallback_models)
        )
        if previous_model and previous_model != row.model:
            fallback_models = [previous_model, *fallback_models]
        fallback_models = [model for model in normalize_model_list(fallback_models) if model != row.model]
        row.fallback_models = serialize_fallback_models(fallback_models)
    elif payload.fallback_models is not None:
        fallback_models = [model for model in normalize_model_list(payload.fallback_models) if model != row.model]
        row.fallback_models = serialize_fallback_models(fallback_models)
    if payload.temperature is not None:
        row.temperature = payload.temperature
    if payload.timeout_seconds is not None:
        row.timeout_seconds = payload.timeout_seconds
    if payload.max_tokens is not None:
        row.max_tokens = payload.max_tokens
    if payload.system_prompt is not None:
        row.system_prompt = payload.system_prompt
    if payload.user_prompt_template is not None:
        row.user_prompt_template = payload.user_prompt_template
    if payload.is_enabled is not None:
        row.is_enabled = payload.is_enabled

    db.commit()
    db.refresh(row)

    config = get_agent_config(db, node_name)
    if not config:
        raise HTTPException(status_code=500, detail="配置保存成功但无法解析，请检查 provider 凭据")
    return _config_to_response(config)


@router.post("/api/admin/agents/{node_name}/test", response_model=AgentTestResponse)
def test_agent(node_name: str, payload: AgentTestRequest, _: str = Depends(get_admin_session), db: Session = Depends(get_db)):
    result = get_llm_client_for_agent(db, node_name)
    if not result:
        return AgentTestResponse(success=False, elapsed_seconds=0, error="Agent 不可用：配置缺失或已禁用")

    client, config = result
    test_payload = {
        "model": config.model,
        "messages": [{"role": "user", "content": payload.test_prompt}],
        "temperature": 0.0,
        "max_tokens": 64,
    }

    start = time.monotonic()
    try:
        data = client.chat_completions(test_payload, trace_id=f"admin_test:{node_name}")
        elapsed = time.monotonic() - start
        choices = data.get("choices") or []
        text = ""
        if choices:
            message = choices[0].get("message") or {}
            content = message.get("content", "")
            text = str(content) if not isinstance(content, str) else content
        return AgentTestResponse(success=True, response_text=text.strip(), elapsed_seconds=round(elapsed, 2))
    except Exception as exc:
        elapsed = time.monotonic() - start
        return AgentTestResponse(success=False, elapsed_seconds=round(elapsed, 2), error=str(exc))


# ── Model Provider routes ─────────────────────────────────────────────────────

@router.get("/api/admin/model-providers", response_model=List[ModelProviderResponse])
def list_model_providers(_: str = Depends(get_admin_session), db: Session = Depends(get_db)):
    if ensure_default_model_providers(db):
        db.commit()
    providers = db.query(ModelProvider).order_by(ModelProvider.id).all()
    return [_provider_to_response(p) for p in providers]


@router.post("/api/admin/model-providers", response_model=ModelProviderResponse, status_code=201)
def create_model_provider(payload: ModelProviderCreate, _: str = Depends(get_admin_session), db: Session = Depends(get_db)):
    ensure_default_model_providers(db)
    existing = db.query(ModelProvider).filter(ModelProvider.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Model provider already exists: {payload.name}")
    p = ModelProvider(
        name=payload.name,
        base_url=payload.base_url.rstrip("/"),
        api_key=payload.api_key,
        is_active=payload.is_active,
        models=json.dumps(payload.models, ensure_ascii=False) if payload.models else None,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _provider_to_response(p)


@router.put("/api/admin/model-providers/{provider_id}", response_model=ModelProviderResponse)
def update_model_provider(provider_id: int, payload: ModelProviderUpdate, _: str = Depends(get_admin_session), db: Session = Depends(get_db)):
    ensure_default_model_providers(db)
    p = db.query(ModelProvider).filter(ModelProvider.id == provider_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Model provider not found")
    if payload.name is not None:
        if p.name in BUILTIN_PROVIDER_NAMES and payload.name != p.name:
            raise HTTPException(status_code=400, detail="Built-in provider name cannot be changed")
        duplicate = db.query(ModelProvider).filter(ModelProvider.name == payload.name, ModelProvider.id != provider_id).first()
        if duplicate:
            raise HTTPException(status_code=409, detail=f"Model provider already exists: {payload.name}")
        in_use = db.query(AgentConfig).filter(AgentConfig.provider == p.name).first()
        if in_use and payload.name != p.name:
            raise HTTPException(status_code=400, detail="Provider is in use by agent configs and cannot be renamed")
        p.name = payload.name
    if payload.base_url is not None:
        p.base_url = payload.base_url.rstrip("/")
    if payload.api_key is not None:
        p.api_key = payload.api_key
    if payload.is_active is not None:
        p.is_active = payload.is_active
    if payload.models is not None:
        p.models = json.dumps(payload.models, ensure_ascii=False) if payload.models else None
    db.commit()
    db.refresh(p)
    return _provider_to_response(p)


@router.delete("/api/admin/model-providers/{provider_id}", status_code=204)
def delete_model_provider(provider_id: int, _: str = Depends(get_admin_session), db: Session = Depends(get_db)):
    ensure_default_model_providers(db)
    p = db.query(ModelProvider).filter(ModelProvider.id == provider_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Model provider not found")
    if p.name in BUILTIN_PROVIDER_NAMES:
        raise HTTPException(status_code=400, detail="Built-in provider cannot be deleted")
    in_use = db.query(AgentConfig).filter(AgentConfig.provider == p.name).first()
    if in_use:
        raise HTTPException(status_code=400, detail="Provider is in use by agent configs and cannot be deleted")
    db.delete(p)
    db.commit()


# ── LLM Stats & Logs routes ───────────────────────────────────────────────────

@router.get("/api/admin/llm-stats/overview", response_model=LlmStatsOverviewResponse)
def get_llm_stats_overview(_: str = Depends(get_admin_session), db: Session = Depends(get_db)):
    total = db.query(func.count(LlmCallLog.id)).scalar() or 0
    success_count = db.query(func.count(LlmCallLog.id)).filter(LlmCallLog.status == "success").scalar() or 0
    error_count = total - success_count
    avg_elapsed = db.query(func.avg(LlmCallLog.elapsed_ms)).scalar() or 0.0
    success_rate = round(success_count / total * 100, 1) if total > 0 else 0.0

    agent_rows = (
        db.query(
            LlmCallLog.agent_node,
            func.count(LlmCallLog.id).label("total"),
            func.sum(case((LlmCallLog.status == "success", 1), else_=0)).label("success"),
        )
        .group_by(LlmCallLog.agent_node)
        .all()
    )

    by_agent = [
        LlmStatsAgentBreakdown(agent_node=r.agent_node, total=r.total, success=r.success or 0)
        for r in agent_rows
    ]

    return LlmStatsOverviewResponse(
        total_calls=total,
        success_count=success_count,
        error_count=error_count,
        success_rate=success_rate,
        avg_elapsed_ms=round(float(avg_elapsed), 1),
        by_agent=by_agent,
    )


@router.get("/api/admin/llm-logs", response_model=LlmLogListResponse)
def list_llm_logs(
    agent_node: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    _: str = Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    query = db.query(LlmCallLog)
    if agent_node:
        query = query.filter(LlmCallLog.agent_node == agent_node)
    if status:
        query = query.filter(LlmCallLog.status == status)
    if date_from:
        try:
            query = query.filter(LlmCallLog.called_at >= datetime.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to) + timedelta(days=1)
            query = query.filter(LlmCallLog.called_at < dt_to)
        except ValueError:
            pass

    total = query.count()
    items = query.order_by(LlmCallLog.called_at.desc()).offset(offset).limit(limit).all()
    return LlmLogListResponse(
        total=total,
        items=[LlmCallLogResponse.model_validate(item) for item in items],
    )
