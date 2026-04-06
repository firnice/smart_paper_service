from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


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
