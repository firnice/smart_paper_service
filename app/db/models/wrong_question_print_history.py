from sqlalchemy import Column, DateTime, ForeignKey, Integer, func
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
        index=True,
    )
    export_id = Column(
        Integer,
        ForeignKey("exports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    printed_at = Column(DateTime, nullable=False, index=True, default=func.now())

    wrong_question = relationship("WrongQuestion", back_populates="print_history")
    export = relationship("Export", back_populates="print_history")
    student = relationship("User", back_populates="print_history")
