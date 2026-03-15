from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
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

PRESET_STUDENT_ACCOUNTS = {
    "test1": {
        "password": "test1",
        "name": "测试学生1",
        "student_no": "TEST001",
        "grade": "三年级",
        "class_name": "1班",
        "school_name": "实验小学",
    },
    "test2": {
        "password": "test2",
        "name": "测试学生2",
        "student_no": "TEST002",
        "grade": "四年级",
        "class_name": "2班",
        "school_name": "实验小学",
    },
    "test3": {
        "password": "test3",
        "name": "测试学生3",
        "student_no": "TEST003",
        "grade": "五年级",
        "class_name": "1班",
        "school_name": "实验小学",
    },
}


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


def _upsert_student_profile(
    db: Session,
    user_id: int,
    student_no: str | None,
    grade: str,
    class_name: str | None = None,
    school_name: str | None = None,
) -> None:
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).first()
    if profile:
        if student_no and not profile.student_no:
            profile.student_no = student_no
        if grade and profile.grade in ("", "未设置"):
            profile.grade = grade
        if class_name and not profile.class_name:
            profile.class_name = class_name
        if school_name and not profile.school_name:
            profile.school_name = school_name
        return

    db.add(
        StudentProfile(
            user_id=user_id,
            student_no=student_no,
            grade=grade,
            class_name=class_name,
            school_name=school_name,
        )
    )


def _find_student_by_student_no(db: Session, student_no: str) -> User | None:
    return (
        db.query(User)
        .options(joinedload(User.student_profile))
        .join(StudentProfile, StudentProfile.user_id == User.id)
        .filter(
            User.role == "student",
            User.status == "active",
            StudentProfile.student_no == student_no,
        )
        .first()
    )


@router.post("/api/auth/student-login", response_model=StudentLoginResponse)
def student_login(payload: StudentLoginRequest, db: Session = Depends(get_db)):
    account = payload.account.strip().lower()
    password = payload.password.strip()
    if not account or not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account and password are required")

    preset = PRESET_STUDENT_ACCOUNTS.get(account)
    if not preset or preset["password"] != password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid student credentials")

    student = _find_student_by_student_no(db, preset["student_no"])
    created = False
    if not student:
        user = User(name=preset["name"], role="student", status="active")
        db.add(user)
        db.flush()
        _upsert_student_profile(
            db=db,
            user_id=user.id,
            student_no=preset["student_no"],
            grade=preset["grade"],
            class_name=preset.get("class_name"),
            school_name=preset.get("school_name"),
        )
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Student profile conflict detected. Please clean orphan student profiles and retry.",
            ) from exc
        student = _reload_student(db, user.id)
        created = True

    return _to_login_response(student, message="Student login verified", created=created)
