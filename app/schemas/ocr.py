from typing import List, Optional

from pydantic import BaseModel

from app.schemas.common import ImageBox


class OcrItem(BaseModel):
    id: int
    text: str
    has_image: bool = False
    image_box: Optional[ImageBox] = None


class OcrExtractResponse(BaseModel):
    items: List[OcrItem]
