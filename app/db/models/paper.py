from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import relationship
from app.db.base import Base


class Paper(Base):
    """试卷/作业表"""

    __tablename__ = "papers"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    original_image_url = Column(String(512), nullable=True)
    status = Column(String(50), default="uploaded")  # uploaded, processed, error
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    questions = relationship("Question", back_populates="paper", cascade="all, delete-orphan")
    wrong_questions = relationship("WrongQuestion", back_populates="paper")
