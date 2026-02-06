from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class StudentProfile(Base):
    """学生扩展资料"""

    __tablename__ = "student_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    student_no = Column(String(64), nullable=True)
    grade = Column(String(20), nullable=False, index=True)
    class_name = Column(String(50), nullable=True)
    school_name = Column(String(255), nullable=True)
    guardian_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="student_profile")
