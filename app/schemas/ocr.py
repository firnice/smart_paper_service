from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import ImageBox


class OcrItem(BaseModel):
    id: int
    text: str
    has_image: bool = False
    question_box: Optional[ImageBox] = None
    image_box: Optional[ImageBox] = None


class OcrItemWithUrls(BaseModel):
    """OCR结果项（包含裁剪后的图片URL）"""
    id: int
    text: str
    has_image: bool = False
    question_box: Optional[ImageBox] = None
    image_box: Optional[ImageBox] = None
    question_image_url: Optional[str] = None  # 题目截图（含文字+图示）
    diagram_image_url: Optional[str] = None  # 图示抠图（尽量去文字）
    diagram_local_image_url: Optional[str] = None  # 本地规则抠图
    diagram_llm_image_url: Optional[str] = None  # LLM识别抠图
    diagram_svg_url: Optional[str] = None  # LLM生成SVG图示
    image_urls: List[str] = Field(default_factory=list)  # 裁剪后的插图URL列表
    clean_source: Optional[str] = None
    clean_fallback: Optional[bool] = None
    clean_fallback_reason: Optional[str] = None
    confidence: Optional[float] = None
    confidence_reasons: List[str] = Field(default_factory=list)
    confidence_breakdown: Optional[Dict[str, float]] = None
    status: Optional[str] = None
    rebuild_json: Optional[Dict[str, Any]] = None


class OcrExtractResponse(BaseModel):
    items: List[OcrItem]


class OcrPipelineMetrics(BaseModel):
    preprocess_ms: int = 0
    ocr_ms: int = 0
    crop_ms: int = 0
    clean_ms: int = 0
    clean_fallback_count: int = 0
    rebuild_ms: int = 0
    manual_refine_count: int = 0
    preprocessing_enabled: bool = False
    preprocessing_applied: bool = False
    preprocessing_engine: Optional[str] = None
    deskew_angle: Optional[float] = None
    preprocessing_fallback_reason: Optional[str] = None


class OcrExtractResponseV2(BaseModel):
    """OCR提取响应（V2版本，包含图片URL和数据库ID）"""
    items: List[OcrItemWithUrls]
    paper_id: int  # 试卷ID
    pipeline_metrics: Optional[OcrPipelineMetrics] = None


class DiagramCropGenerateRequest(BaseModel):
    question_image_url: str
    question_text: str = ""
    item_id: int = 0


class DiagramCropGenerateResponse(BaseModel):
    diagram_llm_image_url: Optional[str] = None


class DiagramSvgGenerateRequest(BaseModel):
    question_text: str
    question_image_url: Optional[str] = None
    diagram_image_url: Optional[str] = None
    item_id: int = 0


class DiagramSvgGenerateResponse(BaseModel):
    diagram_svg_url: Optional[str] = None
