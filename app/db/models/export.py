from sqlalchemy import Column, ForeignKey, Integer, String, Text, Boolean, JSON, DateTime, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class Export(Base):
    """导出任务表"""

    __tablename__ = "exports"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(36), unique=True, index=True, nullable=False)  # UUID
    title = Column(String(255), nullable=False)
    original_text = Column(Text, nullable=False)
    variants_json = Column(JSON, nullable=False)  # 存储变式题列表
    include_images = Column(Boolean, default=True)
    format = Column(String(10), default="pdf")  # pdf, docx
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    download_url = Column(String(512), nullable=True)
    error_message = Column(Text, nullable=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    term_id = Column(Integer, ForeignKey("school_terms.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    term = relationship("SchoolTerm", back_populates="exports")
    print_history = relationship(
        "WrongQuestionPrintHistory",
        back_populates="export",
        cascade="all, delete-orphan",
    )
