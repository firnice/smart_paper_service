from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class WrongQuestion(Base):
    """学生错题主表"""

    __tablename__ = "wrong_questions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=True, index=True)
    title = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True, index=True)
    grade = Column(String(20), nullable=False, index=True)
    question_type = Column(String(50), nullable=True)
    difficulty = Column(String(20), default="medium")
    category_id = Column(Integer, ForeignKey("wrong_question_categories.id"), nullable=True, index=True)
    status = Column(String(20), default="new", index=True)  # new, reviewing, mastered
    source = Column(String(50), default="manual")
    error_count = Column(Integer, default=1)
    is_bookmarked = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    first_error_date = Column(Date, default=func.current_date())
    last_review_date = Column(Date, nullable=True)
    last_practice_result = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    student = relationship("User", foreign_keys=[student_id], back_populates="wrong_questions")
    created_by_user = relationship(
        "User",
        foreign_keys=[created_by_user_id],
        back_populates="created_wrong_questions",
    )
    paper = relationship("Paper", back_populates="wrong_questions")
    question = relationship("Question", back_populates="wrong_questions")
    subject = relationship("Subject", back_populates="wrong_questions")
    category = relationship("WrongQuestionCategory", back_populates="wrong_questions")
    reason_links = relationship(
        "WrongQuestionErrorReason",
        back_populates="wrong_question",
        cascade="all, delete-orphan",
    )
    study_records = relationship(
        "StudyRecord",
        back_populates="wrong_question",
        cascade="all, delete-orphan",
    )
