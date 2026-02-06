from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.base import Base


class Variant(Base):
    """变式题表"""

    __tablename__ = "variants"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    sequence = Column(Integer, nullable=False)  # 变式题序号（1, 2, 3）
    grade = Column(String(50), nullable=True)
    subject = Column(String(50), nullable=True)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=func.now())

    # Relationships
    question = relationship("Question", back_populates="variants")
