from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.db.models import (
    ErrorReason,
    StudyRecord,
    Subject,
    User,
    WrongQuestion,
    WrongQuestionCategory,
    WrongQuestionErrorReason,
)
from app.db.session import get_db
from app.schemas.statistics import (
    CategoryStatisticsItem,
    ErrorReasonStatisticsItem,
    GradeStatisticsItem,
    StatisticsOverviewResponse,
    SubjectStatisticsItem,
    TrendStatisticsItem,
)

router = APIRouter()


def _validate_student(db: Session, student_id: int) -> None:
    user = db.query(User).filter(User.id == student_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student user not found")
    if user.role != "student":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="student_id must be role=student")


def _wrong_question_filters(
    student_id: int,
    start_date: Optional[date],
    end_date: Optional[date],
):
    filters = [WrongQuestion.student_id == student_id]
    if start_date is not None:
        filters.append(WrongQuestion.first_error_date >= start_date)
    if end_date is not None:
        filters.append(WrongQuestion.first_error_date <= end_date)
    return filters


def _study_record_filters(
    student_id: int,
    start_date: Optional[date],
    end_date: Optional[date],
):
    filters = [StudyRecord.student_id == student_id]
    if start_date is not None:
        filters.append(StudyRecord.study_date >= start_date)
    if end_date is not None:
        filters.append(StudyRecord.study_date <= end_date)
    return filters


def _build_subject_breakdown(db: Session, filters: List) -> List[SubjectStatisticsItem]:
    rows = (
        db.query(
            Subject.id.label("subject_id"),
            Subject.code.label("subject_code"),
            Subject.name.label("subject_name"),
            func.count(WrongQuestion.id).label("total"),
            func.coalesce(
                func.sum(case((WrongQuestion.status == "mastered", 1), else_=0)),
                0,
            ).label("mastered"),
        )
        .select_from(WrongQuestion)
        .outerjoin(Subject, WrongQuestion.subject_id == Subject.id)
        .filter(*filters)
        .group_by(Subject.id, Subject.code, Subject.name)
        .order_by(func.count(WrongQuestion.id).desc())
        .all()
    )
    return [
        SubjectStatisticsItem(
            subject_id=row.subject_id,
            subject_code=row.subject_code,
            subject_name=row.subject_name,
            total=int(row.total or 0),
            mastered=int(row.mastered or 0),
        )
        for row in rows
    ]


def _build_grade_breakdown(db: Session, filters: List) -> List[GradeStatisticsItem]:
    rows = (
        db.query(
            WrongQuestion.grade.label("grade"),
            func.count(WrongQuestion.id).label("total"),
        )
        .filter(*filters)
        .group_by(WrongQuestion.grade)
        .order_by(func.count(WrongQuestion.id).desc())
        .all()
    )
    return [GradeStatisticsItem(grade=row.grade, total=int(row.total or 0)) for row in rows]


def _build_category_breakdown(db: Session, filters: List) -> List[CategoryStatisticsItem]:
    rows = (
        db.query(
            WrongQuestionCategory.id.label("category_id"),
            WrongQuestionCategory.name.label("category_name"),
            func.count(WrongQuestion.id).label("total"),
        )
        .select_from(WrongQuestion)
        .outerjoin(WrongQuestionCategory, WrongQuestion.category_id == WrongQuestionCategory.id)
        .filter(*filters)
        .group_by(WrongQuestionCategory.id, WrongQuestionCategory.name)
        .order_by(func.count(WrongQuestion.id).desc())
        .all()
    )
    return [
        CategoryStatisticsItem(
            category_id=row.category_id,
            category_name=row.category_name,
            total=int(row.total or 0),
        )
        for row in rows
    ]


def _build_reason_breakdown(db: Session, filters: List) -> List[ErrorReasonStatisticsItem]:
    rows = (
        db.query(
            ErrorReason.id.label("reason_id"),
            ErrorReason.name.label("reason_name"),
            ErrorReason.category_id.label("category_id"),
            func.count(WrongQuestionErrorReason.wrong_question_id).label("total"),
        )
        .join(
            WrongQuestionErrorReason,
            WrongQuestionErrorReason.error_reason_id == ErrorReason.id,
        )
        .join(WrongQuestion, WrongQuestion.id == WrongQuestionErrorReason.wrong_question_id)
        .filter(*filters)
        .group_by(ErrorReason.id, ErrorReason.name, ErrorReason.category_id)
        .order_by(func.count(WrongQuestionErrorReason.wrong_question_id).desc())
        .all()
    )
    return [
        ErrorReasonStatisticsItem(
            reason_id=row.reason_id,
            reason_name=row.reason_name,
            category_id=row.category_id,
            total=int(row.total or 0),
        )
        for row in rows
    ]


def _build_trend(
    db: Session,
    student_id: int,
    start_date: Optional[date],
    end_date: Optional[date],
) -> List[TrendStatisticsItem]:
    study_filters = _study_record_filters(student_id, start_date, end_date)
    rows = (
        db.query(
            StudyRecord.study_date.label("date"),
            func.count(StudyRecord.id).label("total"),
            func.coalesce(
                func.sum(case((StudyRecord.result == "correct", 1), else_=0)),
                0,
            ).label("correct_count"),
            func.coalesce(
                func.sum(case((StudyRecord.result == "incorrect", 1), else_=0)),
                0,
            ).label("incorrect_count"),
        )
        .filter(*study_filters)
        .group_by(StudyRecord.study_date)
        .order_by(StudyRecord.study_date.asc())
        .all()
    )
    return [
        TrendStatisticsItem(
            date=row.date,
            total=int(row.total or 0),
            correct_count=int(row.correct_count or 0),
            incorrect_count=int(row.incorrect_count or 0),
        )
        for row in rows
    ]


@router.get("/api/statistics/overview", response_model=StatisticsOverviewResponse)
def get_statistics_overview(
    student_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    _validate_student(db, student_id)
    wrong_filters = _wrong_question_filters(student_id, start_date, end_date)
    study_filters = _study_record_filters(student_id, start_date, end_date)

    total_wrong_questions = db.query(func.count(WrongQuestion.id)).filter(*wrong_filters).scalar() or 0
    status_rows = (
        db.query(
            WrongQuestion.status,
            func.count(WrongQuestion.id),
        )
        .filter(*wrong_filters)
        .group_by(WrongQuestion.status)
        .all()
    )
    status_map = {row[0]: int(row[1]) for row in status_rows}

    bookmarked_count = (
        db.query(func.count(WrongQuestion.id))
        .filter(*wrong_filters, WrongQuestion.is_bookmarked.is_(True))
        .scalar()
        or 0
    )
    total_error_count = (
        db.query(func.coalesce(func.sum(WrongQuestion.error_count), 0))
        .filter(*wrong_filters)
        .scalar()
        or 0
    )
    study_records_count = db.query(func.count(StudyRecord.id)).filter(*study_filters).scalar() or 0

    return StatisticsOverviewResponse(
        student_id=student_id,
        total_wrong_questions=int(total_wrong_questions),
        new_count=status_map.get("new", 0),
        reviewing_count=status_map.get("reviewing", 0),
        mastered_count=status_map.get("mastered", 0),
        bookmarked_count=int(bookmarked_count),
        total_error_count=int(total_error_count),
        study_records_count=int(study_records_count),
        subject_breakdown=_build_subject_breakdown(db, wrong_filters),
        grade_breakdown=_build_grade_breakdown(db, wrong_filters),
        category_breakdown=_build_category_breakdown(db, wrong_filters),
        error_reason_breakdown=_build_reason_breakdown(db, wrong_filters),
        trend=_build_trend(db, student_id, start_date, end_date),
    )


@router.get("/api/statistics/by-subject", response_model=List[SubjectStatisticsItem])
def get_statistics_by_subject(
    student_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    _validate_student(db, student_id)
    wrong_filters = _wrong_question_filters(student_id, start_date, end_date)
    return _build_subject_breakdown(db, wrong_filters)


@router.get("/api/statistics/by-grade", response_model=List[GradeStatisticsItem])
def get_statistics_by_grade(
    student_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    _validate_student(db, student_id)
    wrong_filters = _wrong_question_filters(student_id, start_date, end_date)
    return _build_grade_breakdown(db, wrong_filters)


@router.get("/api/statistics/by-category", response_model=List[CategoryStatisticsItem])
def get_statistics_by_category(
    student_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    _validate_student(db, student_id)
    wrong_filters = _wrong_question_filters(student_id, start_date, end_date)
    return _build_category_breakdown(db, wrong_filters)


@router.get("/api/statistics/by-error-reason", response_model=List[ErrorReasonStatisticsItem])
def get_statistics_by_error_reason(
    student_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    _validate_student(db, student_id)
    wrong_filters = _wrong_question_filters(student_id, start_date, end_date)
    return _build_reason_breakdown(db, wrong_filters)


@router.get("/api/statistics/trend", response_model=List[TrendStatisticsItem])
def get_statistics_trend(
    student_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    _validate_student(db, student_id)
    return _build_trend(db, student_id, start_date, end_date)
