from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.school_terms import SchoolTermResponse


class StudentProfilePayload(BaseModel):
    student_no: Optional[str] = Field(default=None, max_length=64)
    grade: str = Field(..., min_length=1, max_length=20)
    class_name: Optional[str] = Field(default=None, max_length=50)
    school_name: Optional[str] = Field(default=None, max_length=255)
    guardian_note: Optional[str] = None
    birth_date: Optional[str] = Field(default=None, max_length=7)  # "YYYY-MM"


class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=32)
    role: str = Field(..., min_length=1, max_length=20)
    status: str = Field(default="active", max_length=20)
    student_profile: Optional[StudentProfilePayload] = None


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=32)
    role: Optional[str] = Field(default=None, min_length=1, max_length=20)
    status: Optional[str] = Field(default=None, max_length=20)
    student_profile: Optional[StudentProfilePayload] = None


class StudentProfileResponse(BaseModel):
    id: int
    user_id: int
    student_no: Optional[str]
    grade: str
    class_name: Optional[str]
    school_name: Optional[str]
    guardian_note: Optional[str]
    birth_date: Optional[str] = None
    current_term_id: Optional[int] = None
    current_term: Optional[SchoolTermResponse] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    id: int
    name: str
    email: Optional[str]
    phone: Optional[str]
    role: str
    status: str
    created_at: datetime
    updated_at: datetime
    student_profile: Optional[StudentProfileResponse] = None

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    total: int
    items: List[UserResponse]


class ParentStudentLinkCreate(BaseModel):
    parent_id: int
    student_id: int
    relation_type: str = Field(default="parent", max_length=50)


class ParentStudentLinkResponse(BaseModel):
    id: int
    parent_id: int
    student_id: int
    relation_type: str
    created_at: datetime

    class Config:
        from_attributes = True


class StudentWithLink(BaseModel):
    link_id: int
    relation_type: str
    student: UserResponse


class ParentWithLink(BaseModel):
    link_id: int
    relation_type: str
    parent: UserResponse
