from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.db.models import StudentProfile, User
from app.db.session import get_db
from app.schemas.auth import (
    StudentLoginRequest,
    StudentLoginResponse,
    StudentLoginStudent,
    StudentLoginStudentProfile,
)

router = APIRouter()


def _to_login_response(student: User, message: str, created: bool = False) -> StudentLoginResponse:
    if not student.student_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student profile is missing",
        )

    return StudentLoginResponse(
        success=True,
        message=message,
        created=created,
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


def _reload_student(db: Session, user_id: int) -> User:
    student = (
        db.query(User)
        .options(joinedload(User.student_profile))
        .filter(User.id == user_id)
        .first()
    )
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return student


@router.post("/api/auth/student-login", response_model=StudentLoginResponse)
def student_login(payload: StudentLoginRequest, db: Session = Depends(get_db)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student name is required",
        )

    students = (
        db.query(User)
        .options(joinedload(User.student_profile))
        .filter(
            User.role == "student",
            User.status == "active",
            User.name == name,
        )
        .order_by(User.id.asc())
        .all()
    )

    # 简化体验：首次登录若不存在学生账号，则自动创建一个基础学生档案。
    if not students:
        user = User(name=name, role="student", status="active")
        db.add(user)
        db.flush()
        db.add(
            StudentProfile(
                user_id=user.id,
                student_no=payload.student_no,
                grade=(payload.grade or "未设置").strip() or "未设置",
            )
        )
        db.commit()
        student = _reload_student(db, user.id)
        return _to_login_response(student, message="首次登录成功，已创建学生档案", created=True)

    # 若提供学号，优先按学号精确匹配；若学生档案未填学号，则自动回填。
    if payload.student_no:
        matched_by_no = [
            item
            for item in students
            if item.student_profile and item.student_profile.student_no == payload.student_no
        ]
        if matched_by_no:
            students = matched_by_no
        elif len(students) == 1 and students[0].student_profile and not students[0].student_profile.student_no:
            students[0].student_profile.student_no = payload.student_no
            db.commit()
            students = [_reload_student(db, students[0].id)]
        else:
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
        db.add(
            StudentProfile(
                user_id=student.id,
                student_no=payload.student_no,
                grade=(payload.grade or "未设置").strip() or "未设置",
            )
        )
        db.commit()
        student = _reload_student(db, student.id)

    # 年级作为辅助信息：若档案仍为默认值则回填，不作为硬性拦截条件。
    if payload.grade and student.student_profile and student.student_profile.grade in ("", "未设置"):
        student.student_profile.grade = payload.grade
        db.commit()
        student = _reload_student(db, student.id)

    return _to_login_response(student, message="Student login verified", created=False)
