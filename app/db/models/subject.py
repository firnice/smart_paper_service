from sqlalchemy import Boolean, Column, DateTime, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class Subject(Base):
    """学科字典"""

    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), nullable=False, unique=True, index=True)  # math/chinese/english
    name = Column(String(100), nullable=False, unique=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    wrong_questions = relationship("WrongQuestion", back_populates="subject")
