from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import (
    StudentLoginRequest,
    StudentLoginResponse,
    StudentLoginStudent,
    StudentLoginStudentProfile,
)

router = APIRouter()


@router.post("/api/auth/student-login", response_model=StudentLoginResponse)
def student_login(payload: StudentLoginRequest, db: Session = Depends(get_db)):
    query = (
        db.query(User)
        .options(joinedload(User.student_profile))
        .filter(
            User.role == "student",
            User.status == "active",
            User.name == payload.name,
        )
    )

    if payload.student_no:
        query = query.filter(User.student_profile.has(student_no=payload.student_no))
    if payload.grade:
        query = query.filter(User.student_profile.has(grade=payload.grade))

    students = query.order_by(User.id.asc()).all()
    if not students:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid student credentials",
        )

    if len(students) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Multiple students matched. Please provide student_no for verification.",
        )

    student = students[0]
    if not student.student_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student profile is missing",
        )

    return StudentLoginResponse(
        success=True,
        message="Student login verified",
        session_token=str(uuid4()),
        student=StudentLoginStudent(
            id=student.id,
            name=student.name,
            role=student.role,
            status=student.status,
            created_at=student.created_at,
            student_profile=StudentLoginStudentProfile(
                student_no=student.student_profile.student_no,
                grade=student.student_profile.grade,
                class_name=student.student_profile.class_name,
                school_name=student.student_profile.school_name,
            ),
        ),
    )
