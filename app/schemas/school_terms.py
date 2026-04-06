from typing import List

from pydantic import BaseModel


class SchoolTermResponse(BaseModel):
    id: int
    name: str
    grade: str
    semester: str
    sort_order: int

    class Config:
        from_attributes = True


class SchoolTermListResponse(BaseModel):
    items: List[SchoolTermResponse]


class SetCurrentTermRequest(BaseModel):
    term_id: int
