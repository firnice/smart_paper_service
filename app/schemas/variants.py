from typing import List, Optional

from pydantic import BaseModel, Field


class VariantsRequest(BaseModel):
    source_text: str
    count: int = Field(3, ge=1, le=5)
    grade: Optional[str] = None
    subject: str = "math"


class VariantsResponse(BaseModel):
    items: List[str]
