from sqlalchemy import Column, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class WrongQuestionErrorReason(Base):
    """错题与错误原因多对多关系"""

    __tablename__ = "wrong_question_error_reasons"

    wrong_question_id = Column(
        Integer,
        ForeignKey("wrong_questions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    error_reason_id = Column(
        Integer,
        ForeignKey("error_reasons.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at = Column(DateTime, default=func.now())

    # Relationships
    wrong_question = relationship("WrongQuestion", back_populates="reason_links")
    error_reason = relationship("ErrorReason", back_populates="wrong_question_links")
