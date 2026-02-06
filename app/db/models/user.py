from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class User(Base):
    """系统用户（学生/家长等）"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=True)
    phone = Column(String(32), unique=True, index=True, nullable=True)
    role = Column(String(20), nullable=False, index=True)  # student, parent, teacher, admin
    status = Column(String(20), default="active", index=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    student_profile = relationship(
        "StudentProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    parent_links = relationship(
        "ParentStudentLink",
        foreign_keys="ParentStudentLink.parent_id",
        back_populates="parent",
        cascade="all, delete-orphan",
    )
    child_links = relationship(
        "ParentStudentLink",
        foreign_keys="ParentStudentLink.student_id",
        back_populates="student",
        cascade="all, delete-orphan",
    )
    wrong_questions = relationship(
        "WrongQuestion",
        foreign_keys="WrongQuestion.student_id",
        back_populates="student",
    )
    created_wrong_questions = relationship(
        "WrongQuestion",
        foreign_keys="WrongQuestion.created_by_user_id",
        back_populates="created_by_user",
    )
    study_records = relationship(
        "StudyRecord",
        foreign_keys="StudyRecord.student_id",
        back_populates="student",
    )
