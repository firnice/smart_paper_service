from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.base import Base


class Question(Base):
    """题目表"""

    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=False, index=True)
    question_no = Column(Integer, nullable=False)  # 题号
    text = Column(Text, nullable=False)  # 题干文本（去手写）
    has_image = Column(Boolean, default=False)
    status = Column(String(50), default="active")  # active, archived
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    paper = relationship("Paper", back_populates="questions")
    images = relationship("QuestionImage", back_populates="question", cascade="all, delete-orphan")
    variants = relationship("Variant", back_populates="question", cascade="all, delete-orphan")
    wrong_questions = relationship("WrongQuestion", back_populates="question")
