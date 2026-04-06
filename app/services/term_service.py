from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.school_term import SchoolTerm
from app.db.models.student_profile import StudentProfile


def infer_term_from_grade_and_date(db: Session, grade: str, ref_date: Optional[date] = None) -> Optional[SchoolTerm]:
    """Given a grade and a reference date, return the matching SchoolTerm.

    上学期: months 9–12, 1
    下学期: months 2–8
    """
    if not grade:
        return None
    month = (ref_date or date.today()).month
    semester = "上" if month in (9, 10, 11, 12, 1) else "下"
    name = f"{grade}{semester}"
    return db.query(SchoolTerm).filter(SchoolTerm.name == name).first()


def get_effective_term(
    db: Session,
    student_profile: Optional[StudentProfile],
    override_term_id: Optional[int] = None,
) -> Optional[SchoolTerm]:
    """Return the term to use:
    1. override_term_id (explicit caller choice)
    2. student_profile.current_term_id (user-selected)
    3. Auto-infer from grade + today
    """
    if override_term_id is not None:
        term = db.query(SchoolTerm).filter(SchoolTerm.id == override_term_id).first()
        if term:
            return term

    if student_profile and student_profile.current_term_id:
        if student_profile.current_term:
            return student_profile.current_term
        term = db.query(SchoolTerm).filter(SchoolTerm.id == student_profile.current_term_id).first()
        if term:
            return term

    if student_profile and student_profile.grade:
        return infer_term_from_grade_and_date(db, student_profile.grade)

    return None


def list_school_terms(db: Session, grade: Optional[str] = None):
    query = db.query(SchoolTerm)
    if grade:
        query = query.filter(SchoolTerm.grade == grade)
    return query.order_by(SchoolTerm.sort_order).all()
