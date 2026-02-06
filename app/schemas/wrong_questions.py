from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class WrongQuestionCreate(BaseModel):
    student_id: int
    content: str = Field(..., min_length=1)
    title: Optional[str] = Field(default=None, max_length=255)
    subject_id: Optional[int] = None
    grade: Optional[str] = Field(default=None, max_length=20)
    question_type: Optional[str] = Field(default=None, max_length=50)
    difficulty: str = Field(default="medium", max_length=20)
    category_id: Optional[int] = None
    error_reason_ids: List[int] = Field(default_factory=list)
    status: str = Field(default="new", max_length=20)
    source: str = Field(default="manual", max_length=50)
    error_count: int = Field(default=1, ge=1)
    is_bookmarked: bool = False
    notes: Optional[str] = None
    first_error_date: Optional[date] = None
    paper_id: Optional[int] = None
    question_id: Optional[int] = None
    created_by_user_id: Optional[int] = None


class WrongQuestionUpdate(BaseModel):
    student_id: Optional[int] = None
    content: Optional[str] = Field(default=None, min_length=1)
    title: Optional[str] = Field(default=None, max_length=255)
    subject_id: Optional[int] = None
    grade: Optional[str] = Field(default=None, max_length=20)
    question_type: Optional[str] = Field(default=None, max_length=50)
    difficulty: Optional[str] = Field(default=None, max_length=20)
    category_id: Optional[int] = None
    error_reason_ids: Optional[List[int]] = None
    status: Optional[str] = Field(default=None, max_length=20)
    source: Optional[str] = Field(default=None, max_length=50)
    error_count: Optional[int] = Field(default=None, ge=1)
    is_bookmarked: Optional[bool] = None
    notes: Optional[str] = None
    first_error_date: Optional[date] = None
    last_review_date: Optional[date] = None
    paper_id: Optional[int] = None
    question_id: Optional[int] = None
    created_by_user_id: Optional[int] = None


class SubjectBrief(BaseModel):
    id: int
    code: str
    name: str


class CategoryBrief(BaseModel):
    id: int
    name: str


class ErrorReasonBrief(BaseModel):
    id: int
    name: str
    category_id: Optional[int] = None


class StudentBrief(BaseModel):
    id: int
    name: str
    role: str
    grade: Optional[str] = None


class WrongQuestionResponse(BaseModel):
    id: int
    student: StudentBrief
    created_by_user_id: Optional[int]
    paper_id: Optional[int]
    question_id: Optional[int]
    title: Optional[str]
    content: str
    subject: Optional[SubjectBrief]
    grade: str
    question_type: Optional[str]
    difficulty: str
    category: Optional[CategoryBrief]
    error_reasons: List[ErrorReasonBrief]
    status: str
    source: str
    error_count: int
    is_bookmarked: bool
    notes: Optional[str]
    first_error_date: Optional[date]
    last_review_date: Optional[date]
    last_practice_result: Optional[str]
    created_at: datetime
    updated_at: datetime


class WrongQuestionListResponse(BaseModel):
    total: int
    items: List[WrongQuestionResponse]


class StudyRecordCreate(BaseModel):
    student_id: Optional[int] = None
    reviewer_user_id: Optional[int] = None
    study_date: Optional[date] = None
    result: str = Field(..., max_length=20)
    time_spent_seconds: Optional[int] = Field(default=None, ge=0)
    mastery_level: Optional[int] = Field(default=None, ge=1, le=5)
    notes: Optional[str] = None


class StudyRecordResponse(BaseModel):
    id: int
    wrong_question_id: int
    student_id: int
    reviewer_user_id: Optional[int]
    study_date: date
    result: str
    time_spent_seconds: Optional[int]
    mastery_level: Optional[int]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class StudyRecordListResponse(BaseModel):
    total: int
    items: List[StudyRecordResponse]
