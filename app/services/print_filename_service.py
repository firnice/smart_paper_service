from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.db.models import StudentProfile, Subject, User, WrongQuestion


def _derive_surname(name: Optional[str]) -> str:
    if not name:
        return "学生"
    stripped = name.strip()
    if not stripped:
        return "学生"
    first_word = stripped.split()[0]
    if not first_word:
        return "学生"
    return first_word[0]


def _load_student_grade_and_semester(db: Session, student_id: Optional[int]) -> tuple[str, str]:
    if student_id is None:
        return "", ""
    profile = (
        db.query(StudentProfile)
        .filter(StudentProfile.user_id == student_id)
        .one_or_none()
    )
    if profile is None:
        return "", ""
    if profile.current_term is not None:
        return (
            profile.current_term.grade or "",
            profile.current_term.semester or "",
        )
    return (profile.grade or "", "")


def _load_subjects_label(db: Session, source_question_ids: Sequence[int]) -> str:
    ids = [sid for sid in source_question_ids if sid is not None]
    if not ids:
        return "未分类"
    rows = (
        db.query(Subject.id, Subject.name)
        .join(WrongQuestion, WrongQuestion.subject_id == Subject.id)
        .filter(WrongQuestion.id.in_(ids))
        .distinct()
        .order_by(Subject.id.asc())
        .all()
    )
    names = [name for _, name in rows if name]
    if not names:
        return "未分类"
    return "_".join(names)


def _load_student_name(db: Session, student_id: Optional[int]) -> Optional[str]:
    if student_id is None:
        return None
    user = db.query(User).filter(User.id == student_id).one_or_none()
    return user.name if user else None


def build_print_pack_filename(
    db: Session,
    student_id: Optional[int],
    source_question_ids: Sequence[int],
    now: Optional[datetime] = None,
) -> str:
    """拼接打印包 PDF 文件名。

    规则：{姓}-{年级}-{学期}-{学科}-{YYYYMMDD-HHMM}.pdf
    空段（年级/学期）会被省略，避免出现双连字符。
    """
    now = now or datetime.now()
    surname = _derive_surname(_load_student_name(db, student_id))
    grade, semester = _load_student_grade_and_semester(db, student_id)
    subjects = _load_subjects_label(db, source_question_ids)
    time_str = now.strftime("%Y%m%d-%H%M")

    segments = [surname, grade, semester, subjects, time_str]
    segments = [seg for seg in segments if seg]
    return "-".join(segments) + ".pdf"
