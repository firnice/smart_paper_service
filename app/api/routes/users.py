from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.db.models import ParentStudentLink, StudentProfile, User
from app.db.session import get_db
from app.schemas.users import (
    ParentStudentLinkCreate,
    ParentStudentLinkResponse,
    ParentWithLink,
    StudentProfileResponse,
    StudentWithLink,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)

router = APIRouter()

VALID_ROLES = {"student", "parent", "teacher", "admin"}
VALID_STATUSES = {"active", "inactive"}


def _validate_role(role: str) -> None:
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{role}'. Valid roles: {sorted(VALID_ROLES)}",
        )


def _validate_status(user_status: str) -> None:
    if user_status not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status '{user_status}'. Valid status: {sorted(VALID_STATUSES)}",
        )


def _get_user_or_404(db: Session, user_id: int) -> User:
    user = (
        db.query(User)
        .options(joinedload(User.student_profile))
        .filter(User.id == user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _to_user_response(user: User) -> UserResponse:
    student_profile = None
    if user.student_profile:
        student_profile = StudentProfileResponse.model_validate(user.student_profile)
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        status=user.status,
        created_at=user.created_at,
        updated_at=user.updated_at,
        student_profile=student_profile,
    )


@router.post("/api/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    _validate_role(payload.role)
    _validate_status(payload.status)

    if payload.role == "student" and payload.student_profile is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student role requires student_profile",
        )
    if payload.role != "student" and payload.student_profile is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only student role can carry student_profile",
        )

    user = User(
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        role=payload.role,
        status=payload.status,
    )
    try:
        db.add(user)
        db.flush()
        if payload.student_profile:
            db.add(
                StudentProfile(
                    user_id=user.id,
                    student_no=payload.student_profile.student_no,
                    grade=payload.student_profile.grade,
                    class_name=payload.student_profile.class_name,
                    school_name=payload.student_profile.school_name,
                    guardian_note=payload.student_profile.guardian_note,
                )
            )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User email/phone already exists",
        ) from exc

    created = _get_user_or_404(db, user.id)
    return _to_user_response(created)


@router.get("/api/users", response_model=UserListResponse)
def list_users(
    role: Optional[str] = None,
    user_status: Optional[str] = Query(default=None, alias="status"),
    keyword: Optional[str] = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(User).options(joinedload(User.student_profile))

    if role:
        _validate_role(role)
        query = query.filter(User.role == role)
    if user_status:
        _validate_status(user_status)
        query = query.filter(User.status == user_status)
    if keyword:
        like_pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                User.name.like(like_pattern),
                User.email.like(like_pattern),
                User.phone.like(like_pattern),
            )
        )

    total = query.count()
    items = query.order_by(User.id.desc()).offset(offset).limit(limit).all()
    return UserListResponse(total=total, items=[_to_user_response(item) for item in items])


@router.get("/api/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    return _to_user_response(_get_user_or_404(db, user_id))


@router.put("/api/users/{user_id}", response_model=UserResponse)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db)):
    user = _get_user_or_404(db, user_id)

    update_data = payload.model_dump(exclude_unset=True)
    has_profile_update = "student_profile" in payload.model_fields_set
    new_profile_payload = payload.student_profile
    if "student_profile" in update_data:
        update_data.pop("student_profile")

    role_after_update = update_data.get("role", user.role)
    status_after_update = update_data.get("status", user.status)
    _validate_role(role_after_update)
    _validate_status(status_after_update)

    if role_after_update == "student":
        if has_profile_update and new_profile_payload is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="student_profile cannot be null for student role",
            )
        if not user.student_profile and new_profile_payload is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Student role requires student_profile",
            )
    else:
        if new_profile_payload is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only student role can carry student_profile",
            )
        if user.student_profile:
            db.delete(user.student_profile)

    for field_name, value in update_data.items():
        setattr(user, field_name, value)

    if new_profile_payload:
        if user.student_profile:
            user.student_profile.student_no = new_profile_payload.student_no
            user.student_profile.grade = new_profile_payload.grade
            user.student_profile.class_name = new_profile_payload.class_name
            user.student_profile.school_name = new_profile_payload.school_name
            user.student_profile.guardian_note = new_profile_payload.guardian_note
        else:
            db.add(
                StudentProfile(
                    user_id=user.id,
                    student_no=new_profile_payload.student_no,
                    grade=new_profile_payload.grade,
                    class_name=new_profile_payload.class_name,
                    school_name=new_profile_payload.school_name,
                    guardian_note=new_profile_payload.guardian_note,
                )
            )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User email/phone already exists",
        ) from exc

    updated = _get_user_or_404(db, user_id)
    return _to_user_response(updated)


@router.post(
    "/api/users/parent-student-links",
    response_model=ParentStudentLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_parent_student_link(payload: ParentStudentLinkCreate, db: Session = Depends(get_db)):
    if payload.parent_id == payload.student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="parent_id and student_id must be different",
        )

    parent = _get_user_or_404(db, payload.parent_id)
    student = _get_user_or_404(db, payload.student_id)

    if parent.role != "parent":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="parent_id must be role=parent")
    if student.role != "student":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="student_id must be role=student")

    link = ParentStudentLink(
        parent_id=payload.parent_id,
        student_id=payload.student_id,
        relation_type=payload.relation_type,
    )
    db.add(link)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Parent-student link already exists",
        ) from exc

    db.refresh(link)
    return link


@router.delete("/api/users/parent-student-links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_parent_student_link(link_id: int, db: Session = Depends(get_db)):
    link = db.query(ParentStudentLink).filter(ParentStudentLink.id == link_id).first()
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent-student link not found")
    db.delete(link)
    db.commit()


@router.get("/api/users/{parent_id}/students", response_model=List[StudentWithLink])
def list_students_by_parent(parent_id: int, db: Session = Depends(get_db)):
    parent = _get_user_or_404(db, parent_id)
    if parent.role != "parent":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is not a parent")

    links = (
        db.query(ParentStudentLink)
        .options(joinedload(ParentStudentLink.student).joinedload(User.student_profile))
        .filter(ParentStudentLink.parent_id == parent_id)
        .order_by(ParentStudentLink.id.desc())
        .all()
    )

    return [
        StudentWithLink(
            link_id=link.id,
            relation_type=link.relation_type,
            student=_to_user_response(link.student),
        )
        for link in links
    ]


@router.get("/api/users/{student_id}/parents", response_model=List[ParentWithLink])
def list_parents_by_student(student_id: int, db: Session = Depends(get_db)):
    student = _get_user_or_404(db, student_id)
    if student.role != "student":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is not a student")

    links = (
        db.query(ParentStudentLink)
        .options(joinedload(ParentStudentLink.parent))
        .filter(ParentStudentLink.student_id == student_id)
        .order_by(ParentStudentLink.id.desc())
        .all()
    )

    return [
        ParentWithLink(
            link_id=link.id,
            relation_type=link.relation_type,
            parent=_to_user_response(link.parent),
        )
        for link in links
    ]
