from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class ParentStudentLink(Base):
    """家长与学生绑定关系"""

    __tablename__ = "parent_student_links"
    __table_args__ = (UniqueConstraint("parent_id", "student_id", name="uq_parent_student_link"),)

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    relation_type = Column(String(50), default="parent")
    created_at = Column(DateTime, default=func.now())

    # Relationships
    parent = relationship("User", foreign_keys=[parent_id], back_populates="parent_links")
    student = relationship("User", foreign_keys=[student_id], back_populates="child_links")
