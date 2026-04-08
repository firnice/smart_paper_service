from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.db.base import Base


class LlmCallLog(Base):
    """LLM 调用日志"""

    __tablename__ = "llm_call_logs"

    id = Column(Integer, primary_key=True, index=True)
    trace_id = Column(String(256), nullable=False, index=True)
    agent_node = Column(String(64), nullable=True, index=True)
    provider = Column(String(32), nullable=False)
    model = Column(String(128), nullable=False)
    student_id = Column(Integer, nullable=True, index=True)

    # success | http_error | network_error | client_error
    status = Column(String(16), nullable=False, index=True)
    http_status = Column(Integer, nullable=True)
    elapsed_ms = Column(Integer, nullable=False)

    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    called_at = Column(DateTime, nullable=False, default=func.now(), index=True)
