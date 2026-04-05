from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, func

from app.db.base import Base


class AgentConfig(Base):
    """LLM Agent 节点配置"""

    __tablename__ = "agent_configs"

    id = Column(Integer, primary_key=True, index=True)
    node_name = Column(String(64), unique=True, nullable=False, index=True)
    display_name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)

    provider = Column(String(32), nullable=False)  # siliconflow, whatai
    model = Column(String(128), nullable=False)
    fallback_models = Column(Text, nullable=True)
    base_url = Column(String(512), nullable=True)  # null = 使用 provider 默认
    api_key_ref = Column(String(64), nullable=True)  # null = 使用 provider 默认

    temperature = Column(Float, default=0.2)
    timeout_seconds = Column(Integer, default=180)
    max_tokens = Column(Integer, nullable=True)

    system_prompt = Column(Text, nullable=True)
    user_prompt_template = Column(Text, nullable=True)

    is_enabled = Column(Boolean, default=True)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
