from typing import List, Optional

from pydantic import BaseModel

from app.schemas.common import ImageBox


class OcrItem(BaseModel):
    id: int
    text: str
    has_image: bool = False
    image_box: Optional[ImageBox] = None


class OcrItemWithUrls(BaseModel):
    """OCR结果项（包含裁剪后的图片URL）"""
    id: int
    text: str
    has_image: bool = False
    image_box: Optional[ImageBox] = None
    image_urls: List[str] = []  # 裁剪后的插图URL列表


class OcrExtractResponse(BaseModel):
    items: List[OcrItem]


class OcrExtractResponseV2(BaseModel):
    """OCR提取响应（V2版本，包含图片URL和数据库ID）"""
    items: List[OcrItemWithUrls]
    paper_id: int  # 试卷ID
