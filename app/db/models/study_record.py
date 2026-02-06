from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class StudyRecord(Base):
    """错题练习记录"""

    __tablename__ = "study_records"

    id = Column(Integer, primary_key=True, index=True)
    wrong_question_id = Column(Integer, ForeignKey("wrong_questions.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    reviewer_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    study_date = Column(Date, default=func.current_date(), index=True)
    result = Column(String(20), nullable=False)  # correct, incorrect, skipped
    time_spent_seconds = Column(Integer, nullable=True)
    mastery_level = Column(Integer, nullable=True)  # 1-5
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    wrong_question = relationship("WrongQuestion", back_populates="study_records")
    student = relationship("User", foreign_keys=[student_id], back_populates="study_records")
    reviewer = relationship("User", foreign_keys=[reviewer_user_id])
