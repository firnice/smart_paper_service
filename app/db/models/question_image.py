from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.base import Base


class QuestionImage(Base):
    """题目插图表"""

    __tablename__ = "question_images"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)
    image_url = Column(String(512), nullable=False)  # 裁剪后的插图 URL
    ymin = Column(Integer, nullable=False)  # 原始坐标
    xmin = Column(Integer, nullable=False)
    ymax = Column(Integer, nullable=False)
    xmax = Column(Integer, nullable=False)
    width = Column(Integer, nullable=True)  # 裁剪后的宽高
    height = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    question = relationship("Question", back_populates="images")
