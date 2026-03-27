import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models.agent_config import AgentConfig
from app.db.session import get_db
from app.schemas.admin import (
    AgentConfigResponse,
    AgentConfigUpdate,
    AgentTestRequest,
    AgentTestResponse,
)
from app.services.agent_config_service import (
    AGENT_DEFAULTS,
    get_agent_config,
    get_llm_client_for_agent,
    list_all_agent_configs,
)

router = APIRouter()


def _config_to_response(config) -> AgentConfigResponse:
    return AgentConfigResponse(
        node_name=config.node_name,
        display_name=config.display_name,
        description=config.description,
        provider=config.provider,
        model=config.model,
        temperature=config.temperature,
        timeout_seconds=config.timeout_seconds,
        max_tokens=config.max_tokens,
        system_prompt=config.system_prompt,
        user_prompt_template=config.user_prompt_template,
        is_enabled=config.is_enabled,
        source=config.source,
    )


@router.get("/api/admin/agents", response_model=list[AgentConfigResponse])
def list_agents(db: Session = Depends(get_db)):
    configs = list_all_agent_configs(db)
    return [_config_to_response(c) for c in configs]


@router.get("/api/admin/agents/{node_name}", response_model=AgentConfigResponse)
def get_agent(node_name: str, db: Session = Depends(get_db)):
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
def update_agent(node_name: str, payload: AgentConfigUpdate, db: Session = Depends(get_db)):
    if node_name not in AGENT_DEFAULTS:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {node_name}")

    row = db.query(AgentConfig).filter(AgentConfig.node_name == node_name).first()
    defaults = AGENT_DEFAULTS[node_name]

    if not row:
        # 首次保存：从 defaults 创建基础记录
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

    # 应用更新
    if payload.display_name is not None:
        row.display_name = payload.display_name
    if payload.description is not None:
        row.description = payload.description
    if payload.provider is not None:
        row.provider = payload.provider
    if payload.model is not None:
        row.model = payload.model
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

    # 重新解析完整配置
    config = get_agent_config(db, node_name)
    if not config:
        raise HTTPException(status_code=500, detail="配置保存成功但无法解析，请检查 provider 凭据")
    return _config_to_response(config)


@router.post("/api/admin/agents/{node_name}/test", response_model=AgentTestResponse)
def test_agent(node_name: str, payload: AgentTestRequest, db: Session = Depends(get_db)):
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
