from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class WrongQuestionCategory(Base):
    """错题分类"""

    __tablename__ = "wrong_question_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    error_reasons = relationship("ErrorReason", back_populates="category")
    wrong_questions = relationship("WrongQuestion", back_populates="category")
