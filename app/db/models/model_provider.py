from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func

from app.db.base import Base


class ModelProvider(Base):
    """模型供应商配置"""

    __tablename__ = "model_providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False, unique=True, index=True)
    base_url = Column(String(512), nullable=False)
    api_key = Column(String(512), nullable=False)
    is_active = Column(Boolean, default=True)
    models = Column(Text, nullable=True)  # JSON array of model name strings

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
