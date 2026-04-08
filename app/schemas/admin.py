from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AgentConfigResponse(BaseModel):
    node_name: str
    display_name: str
    description: str
    provider: str
    model: str
    fallback_models: List[str] = Field(default_factory=list)
    temperature: float
    timeout_seconds: int
    max_tokens: Optional[int] = None
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    is_enabled: bool
    source: str  # "database" | "default"


class AgentConfigUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    fallback_models: Optional[List[str]] = None
    temperature: Optional[float] = None
    timeout_seconds: Optional[int] = None
    max_tokens: Optional[int] = None
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    is_enabled: Optional[bool] = None


class AgentTestRequest(BaseModel):
    test_prompt: str = "请回复'OK'。"


class AgentTestResponse(BaseModel):
    success: bool
    response_text: Optional[str] = None
    elapsed_seconds: float
    error: Optional[str] = None


# ── Model Provider ──────────────────────────────────────────────────────────

class ModelProviderCreate(BaseModel):
    name: str
    base_url: str
    api_key: str
    is_active: bool = True
    models: List[str] = Field(default_factory=list)


class ModelProviderUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    is_active: Optional[bool] = None
    models: Optional[List[str]] = None


class ModelProviderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    base_url: str
    api_key_masked: str
    is_active: bool
    models: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None


# ── LLM Call Logs ───────────────────────────────────────────────────────────

class LlmCallLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trace_id: str
    agent_node: Optional[str] = None
    provider: str
    model: str
    student_id: Optional[int] = None
    status: str
    http_status: Optional[int] = None
    elapsed_ms: int
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    error_message: Optional[str] = None
    called_at: datetime


class LlmLogListResponse(BaseModel):
    total: int
    items: List[LlmCallLogResponse]


class LlmStatsAgentBreakdown(BaseModel):
    agent_node: Optional[str]
    total: int
    success: int


class LlmStatsOverviewResponse(BaseModel):
    total_calls: int
    success_count: int
    error_count: int
    success_rate: float
    avg_elapsed_ms: float
    by_agent: List[LlmStatsAgentBreakdown]
