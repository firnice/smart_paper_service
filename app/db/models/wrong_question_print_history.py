from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class WrongQuestionPrintHistory(Base):
    """记录每次打印包导出时涉及的错题，用于避免重复默认勾选"""

    __tablename__ = "wrong_question_print_history"

    id = Column(Integer, primary_key=True, index=True)
    wrong_question_id = Column(
        Integer,
        ForeignKey("wrong_questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    export_id = Column(
        Integer,
        ForeignKey("exports.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )
    printed_at = Column(DateTime, nullable=False, default=func.now())

    wrong_question = relationship("WrongQuestion", back_populates="print_history")
    export = relationship("Export", back_populates="print_history")
    student = relationship("User", back_populates="print_history")

    __table_args__ = (
        Index("ix_wqph_wrong_question_id", "wrong_question_id"),
        Index("ix_wqph_export_id", "export_id"),
        Index("ix_wqph_student_printed", "student_id", "printed_at"),
    )
