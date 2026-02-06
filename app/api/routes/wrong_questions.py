from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db.models import (
    ErrorReason,
    Paper,
    Question,
    StudyRecord,
    Subject,
    User,
    WrongQuestion,
    WrongQuestionCategory,
    WrongQuestionErrorReason,
)
from app.db.session import get_db
from app.schemas.wrong_questions import (
    CategoryBrief,
    ErrorReasonBrief,
    StudyRecordCreate,
    StudyRecordListResponse,
    StudyRecordResponse,
    StudentBrief,
    SubjectBrief,
    WrongQuestionCreate,
    WrongQuestionListResponse,
    WrongQuestionResponse,
    WrongQuestionUpdate,
)

router = APIRouter()

VALID_WRONG_QUESTION_STATUS = {"new", "reviewing", "mastered"}
VALID_DIFFICULTY = {"easy", "medium", "hard"}
VALID_STUDY_RESULT = {"correct", "incorrect", "skipped"}


def _get_user_or_404(db: Session, user_id: int) -> User:
    user = db.query(User).options(joinedload(User.student_profile)).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _get_wrong_question_or_404(db: Session, wrong_question_id: int) -> WrongQuestion:
    item = (
        db.query(WrongQuestion)
        .options(
            joinedload(WrongQuestion.student).joinedload(User.student_profile),
            joinedload(WrongQuestion.subject),
            joinedload(WrongQuestion.category),
            selectinload(WrongQuestion.reason_links).joinedload(WrongQuestionErrorReason.error_reason),
        )
        .filter(WrongQuestion.id == wrong_question_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wrong question not found")
    return item


def _validate_student_user(student: User) -> None:
    if student.role != "student":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="student_id must be role=student")


def _validate_status(status_value: str) -> None:
    if status_value not in VALID_WRONG_QUESTION_STATUS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid wrong-question status '{status_value}'. Valid status: {sorted(VALID_WRONG_QUESTION_STATUS)}",
        )


def _validate_difficulty(difficulty: str) -> None:
    if difficulty not in VALID_DIFFICULTY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid difficulty '{difficulty}'. Valid values: {sorted(VALID_DIFFICULTY)}",
        )


def _load_subject(db: Session, subject_id: Optional[int]) -> Optional[Subject]:
    if subject_id is None:
        return None
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
    return subject


def _load_category(db: Session, category_id: Optional[int]) -> Optional[WrongQuestionCategory]:
    if category_id is None:
        return None
    category = db.query(WrongQuestionCategory).filter(WrongQuestionCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wrong-question category not found")
    return category


def _load_reasons(db: Session, error_reason_ids: List[int]) -> List[ErrorReason]:
    if not error_reason_ids:
        return []
    reasons = db.query(ErrorReason).filter(ErrorReason.id.in_(error_reason_ids)).all()
    if len(reasons) != len(set(error_reason_ids)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more error reasons not found")
    return reasons


def _validate_source_references(
    db: Session,
    paper_id: Optional[int],
    question_id: Optional[int],
    created_by_user_id: Optional[int],
) -> None:
    if paper_id is not None and not db.query(Paper).filter(Paper.id == paper_id).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found")
    if question_id is not None and not db.query(Question).filter(Question.id == question_id).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    if created_by_user_id is not None and not db.query(User).filter(User.id == created_by_user_id).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="created_by_user not found")


def _build_student_brief(user: User) -> StudentBrief:
    return StudentBrief(
        id=user.id,
        name=user.name,
        role=user.role,
        grade=user.student_profile.grade if user.student_profile else None,
    )


def _serialize_wrong_question(item: WrongQuestion) -> WrongQuestionResponse:
    subject = None
    if item.subject:
        subject = SubjectBrief(id=item.subject.id, code=item.subject.code, name=item.subject.name)

    category = None
    if item.category:
        category = CategoryBrief(id=item.category.id, name=item.category.name)

    reason_items = []
    for link in sorted(item.reason_links, key=lambda x: x.error_reason_id):
        if not link.error_reason:
            continue
        reason_items.append(
            ErrorReasonBrief(
                id=link.error_reason.id,
                name=link.error_reason.name,
                category_id=link.error_reason.category_id,
            )
        )

    return WrongQuestionResponse(
        id=item.id,
        student=_build_student_brief(item.student),
        created_by_user_id=item.created_by_user_id,
        paper_id=item.paper_id,
        question_id=item.question_id,
        title=item.title,
        content=item.content,
        subject=subject,
        grade=item.grade,
        question_type=item.question_type,
        difficulty=item.difficulty,
        category=category,
        error_reasons=reason_items,
        status=item.status,
        source=item.source,
        error_count=item.error_count,
        is_bookmarked=item.is_bookmarked,
        notes=item.notes,
        first_error_date=item.first_error_date,
        last_review_date=item.last_review_date,
        last_practice_result=item.last_practice_result,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _ensure_reason_category_consistency(
    reasons: List[ErrorReason],
    category_id: Optional[int],
) -> None:
    if category_id is None:
        return
    for reason in reasons:
        if reason.category_id is not None and reason.category_id != category_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error reason {reason.id} does not belong to category {category_id}",
            )


@router.post("/api/wrong-questions", response_model=WrongQuestionResponse, status_code=status.HTTP_201_CREATED)
def create_wrong_question(payload: WrongQuestionCreate, db: Session = Depends(get_db)):
    student = _get_user_or_404(db, payload.student_id)
    _validate_student_user(student)
    _validate_status(payload.status)
    _validate_difficulty(payload.difficulty)
    _validate_source_references(db, payload.paper_id, payload.question_id, payload.created_by_user_id)
    _load_subject(db, payload.subject_id)
    _load_category(db, payload.category_id)
    reasons = _load_reasons(db, payload.error_reason_ids)
    _ensure_reason_category_consistency(reasons, payload.category_id)

    resolved_grade = payload.grade or (student.student_profile.grade if student.student_profile else None)
    if not resolved_grade:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="grade is required (or configure student_profile.grade)",
        )

    wrong_question = WrongQuestion(
        student_id=payload.student_id,
        created_by_user_id=payload.created_by_user_id,
        paper_id=payload.paper_id,
        question_id=payload.question_id,
        title=payload.title,
        content=payload.content,
        subject_id=payload.subject_id,
        grade=resolved_grade,
        question_type=payload.question_type,
        difficulty=payload.difficulty,
        category_id=payload.category_id,
        status=payload.status,
        source=payload.source,
        error_count=payload.error_count,
        is_bookmarked=payload.is_bookmarked,
        notes=payload.notes,
        first_error_date=payload.first_error_date or date.today(),
    )
    db.add(wrong_question)
    db.flush()

    for reason in reasons:
        db.add(
            WrongQuestionErrorReason(
                wrong_question_id=wrong_question.id,
                error_reason_id=reason.id,
            )
        )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Failed to create wrong question due to relational constraint",
        ) from exc
    created = _get_wrong_question_or_404(db, wrong_question.id)
    return _serialize_wrong_question(created)


@router.get("/api/wrong-questions", response_model=WrongQuestionListResponse)
def list_wrong_questions(
    student_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    grade: Optional[str] = None,
    status_value: Optional[str] = Query(default=None, alias="status"),
    category_id: Optional[int] = None,
    error_reason_id: Optional[int] = None,
    is_bookmarked: Optional[bool] = None,
    keyword: Optional[str] = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(WrongQuestion)
    if error_reason_id is not None:
        query = query.join(
            WrongQuestionErrorReason,
            WrongQuestionErrorReason.wrong_question_id == WrongQuestion.id,
        ).filter(WrongQuestionErrorReason.error_reason_id == error_reason_id)
    query = query.options(
        joinedload(WrongQuestion.student).joinedload(User.student_profile),
        joinedload(WrongQuestion.subject),
        joinedload(WrongQuestion.category),
        selectinload(WrongQuestion.reason_links).joinedload(WrongQuestionErrorReason.error_reason),
    )

    if student_id is not None:
        query = query.filter(WrongQuestion.student_id == student_id)
    if subject_id is not None:
        query = query.filter(WrongQuestion.subject_id == subject_id)
    if grade is not None:
        query = query.filter(WrongQuestion.grade == grade)
    if status_value is not None:
        _validate_status(status_value)
        query = query.filter(WrongQuestion.status == status_value)
    if category_id is not None:
        query = query.filter(WrongQuestion.category_id == category_id)
    if is_bookmarked is not None:
        query = query.filter(WrongQuestion.is_bookmarked.is_(is_bookmarked))
    if keyword:
        like_pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                WrongQuestion.title.like(like_pattern),
                WrongQuestion.content.like(like_pattern),
                WrongQuestion.notes.like(like_pattern),
            )
        )

    total = query.count()
    items = query.order_by(WrongQuestion.updated_at.desc()).offset(offset).limit(limit).all()
    return WrongQuestionListResponse(
        total=total,
        items=[_serialize_wrong_question(item) for item in items],
    )


@router.get("/api/wrong-questions/{wrong_question_id}", response_model=WrongQuestionResponse)
def get_wrong_question(wrong_question_id: int, db: Session = Depends(get_db)):
    return _serialize_wrong_question(_get_wrong_question_or_404(db, wrong_question_id))


@router.put("/api/wrong-questions/{wrong_question_id}", response_model=WrongQuestionResponse)
def update_wrong_question(wrong_question_id: int, payload: WrongQuestionUpdate, db: Session = Depends(get_db)):
    wrong_question = _get_wrong_question_or_404(db, wrong_question_id)
    update_data = payload.model_dump(exclude_unset=True)
    has_reason_update = "error_reason_ids" in payload.model_fields_set

    if "student_id" in update_data:
        student = _get_user_or_404(db, update_data["student_id"])
        _validate_student_user(student)
    else:
        student = wrong_question.student

    if "status" in update_data:
        _validate_status(update_data["status"])
    if "difficulty" in update_data:
        _validate_difficulty(update_data["difficulty"])

    if "subject_id" in update_data:
        _load_subject(db, update_data["subject_id"])
    if "category_id" in update_data:
        _load_category(db, update_data["category_id"])

    paper_id = update_data["paper_id"] if "paper_id" in update_data else wrong_question.paper_id
    question_id = update_data["question_id"] if "question_id" in update_data else wrong_question.question_id
    created_by_user_id = (
        update_data["created_by_user_id"]
        if "created_by_user_id" in update_data
        else wrong_question.created_by_user_id
    )
    _validate_source_references(db, paper_id, question_id, created_by_user_id)

    if "grade" in update_data and not update_data["grade"]:
        fallback_grade = student.student_profile.grade if student.student_profile else None
        if not fallback_grade:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="grade cannot be empty for student",
            )
        update_data["grade"] = fallback_grade

    for field_name, value in update_data.items():
        if field_name == "error_reason_ids":
            continue
        setattr(wrong_question, field_name, value)

    if has_reason_update:
        reason_ids = payload.error_reason_ids or []
        reasons = _load_reasons(db, reason_ids)
        effective_category_id = wrong_question.category_id
        if "category_id" in update_data:
            effective_category_id = update_data["category_id"]
        _ensure_reason_category_consistency(reasons, effective_category_id)
        wrong_question.reason_links = [
            WrongQuestionErrorReason(error_reason_id=reason.id) for reason in reasons
        ]

    db.commit()
    updated = _get_wrong_question_or_404(db, wrong_question_id)
    return _serialize_wrong_question(updated)


@router.delete("/api/wrong-questions/{wrong_question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_wrong_question(wrong_question_id: int, db: Session = Depends(get_db)):
    wrong_question = db.query(WrongQuestion).filter(WrongQuestion.id == wrong_question_id).first()
    if not wrong_question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wrong question not found")
    db.delete(wrong_question)
    db.commit()


@router.post(
    "/api/wrong-questions/{wrong_question_id}/study-records",
    response_model=StudyRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_study_record(
    wrong_question_id: int,
    payload: StudyRecordCreate,
    db: Session = Depends(get_db),
):
    wrong_question = _get_wrong_question_or_404(db, wrong_question_id)

    if payload.result not in VALID_STUDY_RESULT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid study result '{payload.result}'. Valid results: {sorted(VALID_STUDY_RESULT)}",
        )

    student_id = payload.student_id or wrong_question.student_id
    if student_id != wrong_question.student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="study_record.student_id must match wrong_question.student_id",
        )

    _get_user_or_404(db, student_id)

    if payload.reviewer_user_id is not None:
        _get_user_or_404(db, payload.reviewer_user_id)

    study_date = payload.study_date or date.today()
    record = StudyRecord(
        wrong_question_id=wrong_question.id,
        student_id=student_id,
        reviewer_user_id=payload.reviewer_user_id,
        study_date=study_date,
        result=payload.result,
        time_spent_seconds=payload.time_spent_seconds,
        mastery_level=payload.mastery_level,
        notes=payload.notes,
    )
    db.add(record)

    wrong_question.last_review_date = study_date
    wrong_question.last_practice_result = payload.result
    if payload.result == "incorrect":
        wrong_question.status = "reviewing"
        wrong_question.error_count += 1
    elif payload.result == "correct":
        if payload.mastery_level is not None and payload.mastery_level >= 4:
            wrong_question.status = "mastered"
        elif wrong_question.status == "new":
            wrong_question.status = "reviewing"

    db.commit()
    db.refresh(record)
    return record


@router.get(
    "/api/wrong-questions/{wrong_question_id}/study-records",
    response_model=StudyRecordListResponse,
)
def list_study_records(
    wrong_question_id: int,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    _get_wrong_question_or_404(db, wrong_question_id)

    query = db.query(StudyRecord).filter(StudyRecord.wrong_question_id == wrong_question_id)
    total = query.count()
    items = (
        query.order_by(StudyRecord.study_date.desc(), StudyRecord.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return StudyRecordListResponse(
        total=total,
        items=[StudyRecordResponse.model_validate(item) for item in items],
    )
