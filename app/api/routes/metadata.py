from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import ErrorReason, Subject, WrongQuestionCategory
from app.db.session import get_db
from app.schemas.metadata import (
    ErrorReasonCreate,
    ErrorReasonListResponse,
    ErrorReasonResponse,
    SubjectCreate,
    SubjectListResponse,
    SubjectResponse,
    WrongQuestionCategoryCreate,
    WrongQuestionCategoryListResponse,
    WrongQuestionCategoryResponse,
)

router = APIRouter()


@router.get("/api/subjects", response_model=SubjectListResponse)
def list_subjects(
    active_only: bool = True,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Subject)
    if active_only:
        query = query.filter(Subject.is_active.is_(True))
    total = query.count()
    items = query.order_by(Subject.id.asc()).offset(offset).limit(limit).all()
    return SubjectListResponse(
        total=total,
        items=[SubjectResponse.model_validate(item) for item in items],
    )


@router.post("/api/subjects", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
def create_subject(payload: SubjectCreate, db: Session = Depends(get_db)):
    subject = Subject(code=payload.code.strip(), name=payload.name.strip(), is_active=payload.is_active)
    db.add(subject)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Subject code/name already exists") from exc
    db.refresh(subject)
    return subject


@router.get("/api/wrong-question-categories", response_model=WrongQuestionCategoryListResponse)
def list_wrong_question_categories(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(WrongQuestionCategory)
    total = query.count()
    items = query.order_by(WrongQuestionCategory.id.asc()).offset(offset).limit(limit).all()
    return WrongQuestionCategoryListResponse(
        total=total,
        items=[WrongQuestionCategoryResponse.model_validate(item) for item in items],
    )


@router.post(
    "/api/wrong-question-categories",
    response_model=WrongQuestionCategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_wrong_question_category(payload: WrongQuestionCategoryCreate, db: Session = Depends(get_db)):
    category = WrongQuestionCategory(name=payload.name.strip(), description=payload.description)
    db.add(category)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Category name already exists") from exc
    db.refresh(category)
    return category


@router.get("/api/error-reasons", response_model=ErrorReasonListResponse)
def list_error_reasons(
    category_id: Optional[int] = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(ErrorReason)
    if category_id is not None:
        query = query.filter(ErrorReason.category_id == category_id)
    total = query.count()
    items = query.order_by(ErrorReason.id.asc()).offset(offset).limit(limit).all()
    return ErrorReasonListResponse(
        total=total,
        items=[ErrorReasonResponse.model_validate(item) for item in items],
    )


@router.post("/api/error-reasons", response_model=ErrorReasonResponse, status_code=status.HTTP_201_CREATED)
def create_error_reason(payload: ErrorReasonCreate, db: Session = Depends(get_db)):
    if payload.category_id is not None:
        category = (
            db.query(WrongQuestionCategory)
            .filter(WrongQuestionCategory.id == payload.category_id)
            .first()
        )
        if not category:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    reason = ErrorReason(
        name=payload.name.strip(),
        description=payload.description,
        category_id=payload.category_id,
    )
    db.add(reason)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Error reason already exists in this category",
        ) from exc
    db.refresh(reason)
    return reason
