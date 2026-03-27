from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class TrendAnalysisRequest(BaseModel):
    student_id: int
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    subject_filter: Optional[str] = None


class TrendAnalysisResponse(BaseModel):
    id: int
    student_id: int
    status: str
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    analysis_result: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None


class TrendAnalysisCreateResponse(BaseModel):
    id: int
    status: str
