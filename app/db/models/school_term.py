from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class SchoolTerm(Base):
    """学期字典表（小学一年级上～六年级下，共12条）"""

    __tablename__ = "school_terms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(20), nullable=False, unique=True)   # "三年级上"
    grade = Column(String(20), nullable=False, index=True)   # "三年级"
    semester = Column(String(4), nullable=False)              # "上" or "下"
    sort_order = Column(Integer, nullable=False, index=True)  # 1–12

    # Back-references
    student_profiles = relationship("StudentProfile", back_populates="current_term")
    wrong_questions = relationship("WrongQuestion", back_populates="term")
    exports = relationship("Export", back_populates="term")
