from typing import List, Optional

from pydantic import BaseModel


class ExportRequest(BaseModel):
    title: str
    original_text: str
    variants: List[str]
    include_images: bool = True


class ExportResponse(BaseModel):
    job_id: str
    status: str
    download_url: Optional[str] = None
