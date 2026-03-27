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


class VariantItemResponse(BaseModel):
    text: str
    answer: str = ""
    hint: str = ""


class VariantsForQuestionResponse(BaseModel):
    source_question_id: int
    items: List[VariantItemResponse]
