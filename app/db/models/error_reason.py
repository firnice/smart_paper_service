from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class ErrorReason(Base):
    """错误原因字典"""

    __tablename__ = "error_reasons"
    __table_args__ = (UniqueConstraint("name", "category_id", name="uq_error_reason_name_category"),)

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    category_id = Column(Integer, ForeignKey("wrong_question_categories.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    category = relationship("WrongQuestionCategory", back_populates="error_reasons")
    wrong_question_links = relationship(
        "WrongQuestionErrorReason",
        back_populates="error_reason",
        cascade="all, delete-orphan",
    )
