from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.logger import logger
from app.db.models.trend_analysis import TrendAnalysis
from app.db.models.user import User
from app.db.session import get_db
from app.core.student_auth import get_student_session
from app.schemas.analysis import (
    TrendAnalysisCreateResponse,
    TrendAnalysisRequest,
    TrendAnalysisResponse,
)
from app.services.trend_analysis_service import run_trend_analysis_task

router = APIRouter()


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _validate_student(db: Session, student_id: int) -> None:
    user = db.query(User).filter(User.id == student_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student user not found")
    if user.role != "student":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="student_id must be role=student")


def _to_response(analysis: TrendAnalysis) -> TrendAnalysisResponse:
    """将 DB 模型转为响应 schema。"""
    result_dict = None
    if analysis.analysis_result:
        try:
            result_dict = json.loads(analysis.analysis_result)
        except (json.JSONDecodeError, TypeError):
            result_dict = {"raw_text": analysis.analysis_result}

    return TrendAnalysisResponse(
        id=analysis.id,
        student_id=analysis.student_id,
        status=analysis.status,
        created_at=str(analysis.created_at) if analysis.created_at else None,
        completed_at=str(analysis.completed_at) if analysis.completed_at else None,
        analysis_result=result_dict,
        error_message=analysis.error_message,
    )


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------


@router.post("/api/analysis/trend", response_model=TrendAnalysisCreateResponse)
def create_trend_analysis(
    payload: TrendAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_student_id: int = Depends(get_student_session),
):
    """发起趋势分析（异步后台执行）。"""
    if payload.student_id != current_student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    _validate_student(db, payload.student_id)

    analysis = TrendAnalysis(
        student_id=payload.student_id,
        status="pending",
        start_date=payload.start_date,
        end_date=payload.end_date,
        subject_filter=payload.subject_filter,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    logger.info("Created trend analysis id=%s for student_id=%s", analysis.id, payload.student_id)

    # 加入后台任务
    background_tasks.add_task(run_trend_analysis_task, analysis.id)

    return TrendAnalysisCreateResponse(id=analysis.id, status=analysis.status)


@router.get("/api/analysis/trend/latest", response_model=Optional[TrendAnalysisResponse])
def get_latest_trend_analysis(
    db: Session = Depends(get_db),
    student_id: int = Depends(get_student_session),
):
    """查询学生最新已完成的趋势分析。"""
    _validate_student(db, student_id)

    analysis = (
        db.query(TrendAnalysis)
        .filter(
            TrendAnalysis.student_id == student_id,
            TrendAnalysis.status == "completed",
        )
        .order_by(TrendAnalysis.created_at.desc())
        .first()
    )

    if not analysis:
        raise HTTPException(status_code=404, detail="No completed analysis found")

    return _to_response(analysis)


@router.get("/api/analysis/trend/{analysis_id}", response_model=TrendAnalysisResponse)
def get_trend_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_student_id: int = Depends(get_student_session),
):
    """查询特定分析结果。"""
    analysis = db.query(TrendAnalysis).filter(TrendAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.student_id != current_student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return _to_response(analysis)


@router.get("/api/analysis/trend", response_model=List[TrendAnalysisResponse])
def list_trend_analyses(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    student_id: int = Depends(get_student_session),
):
    """列出学生的历史分析报告。"""
    _validate_student(db, student_id)

    analyses = (
        db.query(TrendAnalysis)
        .filter(TrendAnalysis.student_id == student_id)
        .order_by(TrendAnalysis.created_at.desc())
        .limit(limit)
        .all()
    )

    return [_to_response(a) for a in analyses]
