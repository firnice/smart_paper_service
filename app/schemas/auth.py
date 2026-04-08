from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class StudentLoginRequest(BaseModel):
    account: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=64)


class StudentLoginStudentProfile(BaseModel):
    student_no: Optional[str]
    grade: str
    class_name: Optional[str]
    school_name: Optional[str]


class StudentLoginStudent(BaseModel):
    id: int
    name: str
    role: str
    status: str
    created_at: datetime
    student_profile: StudentLoginStudentProfile


class StudentLoginResponse(BaseModel):
    success: bool
    message: str
    created: bool = False
    session_token: str
    student: StudentLoginStudent


class StudentLoginPresetAccount(BaseModel):
    account: str
    password: str
    note: str


class StudentLoginConfigResponse(BaseModel):
    mode: str
    show_presets: bool = False
    title: str
    subtitle: str
    help_text: str
    preset_accounts: List[StudentLoginPresetAccount] = Field(default_factory=list)


class AdminLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class AdminLoginResponse(BaseModel):
    success: bool
    session_token: str
    role: str
