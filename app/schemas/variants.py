from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class VariantsRequest(BaseModel):
    source_text: str
    count: int = Field(3, ge=1, le=5)
    grade: Optional[str] = None
    subject: str = "math"


class VariantsResponse(BaseModel):
    items: List[str]


# ---------------------------------------------------------------------------
# 新版举一反三（结构化）
# ---------------------------------------------------------------------------


class VariantsForQuestionRequest(BaseModel):
    wrong_question_id: int
    count: int = Field(3, ge=1, le=5)
    prompt: Optional[str] = None
    include_images: bool = False


class VariantItemResponse(BaseModel):
    id: str
    text: str
    answer: str = ""
    hint: str = ""
    svg: Optional[str] = None


class VariantSourceQuestionResponse(BaseModel):
    id: int
    text: str
    image_url: Optional[str] = None
    reference_answer: Optional[str] = None
    analysis: Optional[str] = None
    svg: Optional[str] = None


class VariantsForQuestionResponse(BaseModel):
    source_question_id: int
    used_prompt: str
    source_question: VariantSourceQuestionResponse
    items: List[VariantItemResponse]
