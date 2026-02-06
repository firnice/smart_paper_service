from datetime import date
from typing import List, Optional

from pydantic import BaseModel


class SubjectStatisticsItem(BaseModel):
    subject_id: Optional[int]
    subject_code: Optional[str]
    subject_name: Optional[str]
    total: int
    mastered: int


class GradeStatisticsItem(BaseModel):
    grade: str
    total: int


class CategoryStatisticsItem(BaseModel):
    category_id: Optional[int]
    category_name: Optional[str]
    total: int


class ErrorReasonStatisticsItem(BaseModel):
    reason_id: int
    reason_name: str
    category_id: Optional[int]
    total: int


class TrendStatisticsItem(BaseModel):
    date: date
    total: int
    correct_count: int
    incorrect_count: int


class StatisticsOverviewResponse(BaseModel):
    student_id: int
    total_wrong_questions: int
    new_count: int
    reviewing_count: int
    mastered_count: int
    bookmarked_count: int
    total_error_count: int
    study_records_count: int
    subject_breakdown: List[SubjectStatisticsItem]
    grade_breakdown: List[GradeStatisticsItem]
    category_breakdown: List[CategoryStatisticsItem]
    error_reason_breakdown: List[ErrorReasonStatisticsItem]
    trend: List[TrendStatisticsItem]
