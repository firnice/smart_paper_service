from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.db.base import Base


class TrendAnalysis(Base):
    """学生错题趋势分析记录"""

    __tablename__ = "trend_analyses"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, nullable=False, index=True)
    status = Column(String(20), default="pending", nullable=False, index=True)
    start_date = Column(String(10), nullable=True)
    end_date = Column(String(10), nullable=True)
    subject_filter = Column(String(64), nullable=True)
    input_snapshot = Column(Text, nullable=True)
    analysis_result = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)
