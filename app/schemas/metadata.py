from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class SubjectCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    is_active: bool = True


class SubjectResponse(BaseModel):
    id: int
    code: str
    name: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SubjectListResponse(BaseModel):
    total: int
    items: List[SubjectResponse]


class WrongQuestionCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


class WrongQuestionCategoryResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class WrongQuestionCategoryListResponse(BaseModel):
    total: int
    items: List[WrongQuestionCategoryResponse]


class ErrorReasonCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    category_id: Optional[int] = None


class ErrorReasonResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    category_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class ErrorReasonListResponse(BaseModel):
    total: int
    items: List[ErrorReasonResponse]
