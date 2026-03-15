from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class ExportQuestionItem(BaseModel):
    title: Optional[str] = None
    content: str = Field(..., min_length=1)
    subject: Optional[str] = None
    category: Optional[str] = None


class ExportRequest(BaseModel):
    title: str
    original_text: Optional[str] = None
    variants: List[str] = Field(default_factory=list)
    include_images: bool = True

    # 新增：多题打印包模式
    mode: str = Field(default="single", max_length=20)
    question_items: List[ExportQuestionItem] = Field(default_factory=list)
    hide_answers: bool = True

    @model_validator(mode="after")
    def validate_payload(self):
        if self.question_items:
            return self
        if self.original_text and self.original_text.strip():
            return self
        raise ValueError("Either original_text or question_items is required")


class ExportResponse(BaseModel):
    job_id: str
    status: str
    download_url: Optional[str] = None
