from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.db.models import User
from app.db.models.school_term import SchoolTerm
from app.db.session import get_db
from app.core.student_auth import get_student_session
from app.schemas.school_terms import SchoolTermListResponse, SchoolTermResponse, SetCurrentTermRequest
from app.schemas.users import UserResponse
from app.services import term_service

router = APIRouter()


@router.get("/api/school-terms", response_model=SchoolTermListResponse)
def list_school_terms(grade: Optional[str] = None, db: Session = Depends(get_db)):
    """返回所有学期（小学12个），可按年级过滤"""
    items = term_service.list_school_terms(db, grade)
    return SchoolTermListResponse(items=[SchoolTermResponse.model_validate(t) for t in items])


@router.put("/api/users/{user_id}/term")
def set_current_term(user_id: int, payload: SetCurrentTermRequest, db: Session = Depends(get_db), current_student_id: int = Depends(get_student_session)):
    """设置学生的当前学期"""
    if user_id != current_student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot modify another student's term")
    user = (
        db.query(User)
        .options(joinedload(User.student_profile))
        .filter(User.id == user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.role != "student":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only student users have a term")
    if not user.student_profile:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Student profile not found")

    term = db.query(SchoolTerm).filter(SchoolTerm.id == payload.term_id).first()
    if not term:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="School term not found")

    user.student_profile.current_term_id = payload.term_id
    db.commit()

    return SchoolTermResponse.model_validate(term)
