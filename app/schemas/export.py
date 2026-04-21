from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class ExportQuestionItem(BaseModel):
    title: Optional[str] = None
    content: str = Field(..., min_length=1)
    subject: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None


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


class PrintPackPaperMeta(BaseModel):
    student_name: Optional[str] = None
    class_name: Optional[str] = None
    date: Optional[str] = None


class PrintPackItem(BaseModel):
    id: str = Field(..., min_length=1)
    source_question_id: Optional[int] = None
    type: str = Field(..., max_length=10)
    order: int = Field(..., ge=1)
    text: str = Field(..., min_length=1)
    answer: Optional[str] = None
    image_url: Optional[str] = None

    @model_validator(mode="after")
    def validate_type(self):
        if self.type not in {"orig", "ai"}:
            raise ValueError("type must be one of: orig, ai")
        return self


class PrintPackExportRequest(BaseModel):
    student_id: Optional[int] = None
    title: str = Field(..., min_length=1)
    answer_mode: str = Field(default="hidden", max_length=20)
    paper_meta: PrintPackPaperMeta = Field(default_factory=PrintPackPaperMeta)
    items: List[PrintPackItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_payload(self):
        if self.answer_mode not in {"hidden", "inline", "sheet"}:
            raise ValueError("answer_mode must be one of: hidden, inline, sheet")
        if not self.items:
            raise ValueError("items is required")
        return self


class PrintPackExportResponse(BaseModel):
    id: int
    status: str
    download_url: Optional[str] = None
    filename: Optional[str] = None
