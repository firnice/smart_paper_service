import base64
import binascii
import mimetypes
import time
from pathlib import Path
from urllib.parse import unquote_to_bytes, urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logger import logger
from app.schemas.ocr import (
    DiagramCropGenerateRequest,
    DiagramCropGenerateResponse,
    DiagramSvgGenerateRequest,
    DiagramSvgGenerateResponse,
    OcrExtractResponse,
    OcrExtractResponseV2,
    OcrItemWithUrls,
    OcrPipelineMetrics,
    QuestionAnalyzeRequest,
    QuestionAnalyzeResponse,
)
from app.services import diagram_llm_service
from app.services import ocr_service
from app.services import question_analysis_service
from app.db.models.paper import Paper
from app.db.models.question import Question
from app.db.session import get_db
from app.services.image_service import prepare_image_for_ocr_pipeline
from app.services.storage_service import get_storage_service

router = APIRouter()


def _load_asset_bytes(asset_url: str) -> tuple[bytes, str]:
    value = str(asset_url or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="Missing asset url.")

    if value.startswith("data:"):
        header, sep, raw = value.partition(",")
        if not sep:
            raise HTTPException(status_code=400, detail="Invalid data url.")
        content_type = header[5:].split(";", 1)[0] or "application/octet-stream"
        try:
            if ";base64" in header:
                return base64.b64decode(raw), content_type
            return unquote_to_bytes(raw), content_type
        except (ValueError, binascii.Error) as exc:
            raise HTTPException(status_code=400, detail="Invalid data url payload.") from exc

    parsed = urlparse(value)
    path = parsed.path or value
    if not path.startswith("/static/"):
        raise HTTPException(status_code=400, detail="Only local static asset urls are supported.")

    relative_path = path[len("/static/"):].lstrip("/")
    storage_root = Path(settings.storage_base_dir).resolve()
    file_path = (storage_root / relative_path).resolve()
    try:
        file_path.relative_to(storage_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid asset path.") from exc

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Asset file not found.")

    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    return file_path.read_bytes(), content_type

@router.post(
    "/api/ocr/extract",
    response_model=OcrExtractResponseV2,
    response_model_exclude_none=False,
)
async def extract_questions(
    file: UploadFile = File(...),
    prompt: str | None = Form(default=None),
    db: Session = Depends(get_db)
):
    """
    题目提取（完整流程，接口保持不变，内部使用多模态 LLM）

    流程：
    1. 保存原始图片到存储
    2. 创建 Paper 记录
    3. 调用多模态 LLM 识别题目并分析错题信息
    4. 对每个题目创建 Question 记录
    5. 提交数据库事务
    6. 返回题目列表
    """
    content_type = file.content_type or "image/png"
    filename = file.filename or "upload.png"

    try:
        # 读取上传的图片
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Empty upload.")

        logger.info(
            "OCR upload received filename=%s bytes=%d content_type=%s custom_prompt=%s",
            filename,
            len(image_bytes),
            content_type,
            "yes" if (prompt or "").strip() else "no",
        )

        preprocess_start_at = time.perf_counter()
        ocr_image_bytes, ocr_content_type, ocr_filename, preprocess_meta = prepare_image_for_ocr_pipeline(
            image_bytes,
            content_type,
            filename,
            enable_local_preprocess=settings.enable_local_preprocess,
        )
        preprocess_ms = int((time.perf_counter() - preprocess_start_at) * 1000)

        storage = get_storage_service()

        # 1. 保存原始图片到存储
        paper_url = storage.upload_paper_image(ocr_image_bytes, ocr_filename)
        logger.info("Saved original paper image: %s", paper_url)

        # 2. 创建 Paper 记录
        paper = Paper(
            title=ocr_filename or "Untitled",
            original_image_url=paper_url,
            status="processing"
        )
        db.add(paper)
        db.flush()  # 获取 paper.id
        logger.info("Created Paper record: id=%d", paper.id)

        # 3. LLM 识别题目
        ocr_start_at = time.perf_counter()
        ocr_items, effective_prompt = ocr_service.extract_questions(
            ocr_image_bytes,
            ocr_content_type,
            ocr_filename,
            prompt=prompt,
            db=db,
        )
        ocr_ms = int((time.perf_counter() - ocr_start_at) * 1000)
        logger.info("LLM extracted %d questions", len(ocr_items))

        # 4. 保存题目记录并返回结构化结果
        result_items = []
        for item in ocr_items:
            # 创建 Question 记录
            question = Question(
                paper_id=paper.id,
                question_no=item.id,
                text=item.text,
                has_image=bool(item.has_image),
            )
            db.add(question)
            db.flush()  # 获取 question.id

            # 构建响应项
            result_items.append(
                OcrItemWithUrls(
                    id=item.id,
                    text=item.text,
                    subject_tag=item.subject_tag,
                    is_wrong=item.is_wrong,
                    wrong_reason=item.wrong_reason,
                    correction_suggestion=item.correction_suggestion,
                    has_image=bool(item.has_image),
                    question_box=item.question_box,
                    image_box=item.image_box,
                    question_image_url=None,
                    diagram_image_url=None,
                    diagram_local_image_url=None,
                    diagram_llm_image_url=None,
                    diagram_svg_url=None,
                    image_urls=[],
                    clean_source=None,
                    clean_fallback=None,
                    clean_fallback_reason=None,
                    rebuild_json=None,
                    confidence=None,
                    confidence_reasons=[],
                    confidence_breakdown=None,
                    status="ok",
                )
            )

        pipeline_metrics = OcrPipelineMetrics(
            preprocess_ms=preprocess_ms,
            ocr_ms=ocr_ms,
            crop_ms=0,
            clean_ms=0,
            clean_fallback_count=0,
            rebuild_ms=0,
            manual_refine_count=0,
            preprocessing_enabled=bool(preprocess_meta.get("preprocessing_enabled")),
            preprocessing_applied=bool(preprocess_meta.get("preprocessing_applied")),
            preprocessing_engine=preprocess_meta.get("preprocessing_engine"),
            deskew_angle=preprocess_meta.get("deskew_angle"),
            preprocessing_fallback_reason=preprocess_meta.get("preprocessing_fallback_reason"),
        )

        # 5. 更新 Paper 状态并提交
        paper.status = "processed"
        db.commit()

        logger.info(
            "OCR-LLM processing completed: paper_id=%d, questions=%d preprocess_ms=%d ocr_ms=%d preprocessing_applied=%s",
            paper.id,
            len(result_items),
            pipeline_metrics.preprocess_ms,
            pipeline_metrics.ocr_ms,
            pipeline_metrics.preprocessing_applied,
        )

        response_prompt = effective_prompt
        logger.info(
            "OCR response prompt prepared paper_id=%d prompt=%r",
            paper.id,
            response_prompt,
        )
        payload = OcrExtractResponseV2(
            items=result_items,
            paper_id=paper.id,
            used_prompt=response_prompt,
            prompt=response_prompt,
            pipeline_metrics=pipeline_metrics,
        )
        return JSONResponse(content=payload.model_dump(mode="json", exclude_none=False))

    except HTTPException:
        db.rollback()
        raise
    except RuntimeError as exc:
        db.rollback()
        logger.exception("OCR service failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("OCR processing failed")
        raise HTTPException(status_code=500, detail="Internal server error.") from exc


@router.post(
    "/api/ocr/extract/simple",
    response_model=OcrExtractResponse,
    response_model_exclude_none=False,
)
async def extract_questions_simple(
    file: UploadFile = File(...),
    prompt: str | None = Form(default=None),
):
    """
    题目提取（简单版本，不入库）

    仅执行多模态 LLM 识题，不保存到数据库，用于快速测试。
    """
    content_type = file.content_type or "image/png"
    filename = file.filename or "upload.png"
    try:
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Empty upload.")

        logger.info(
            "OCR simple upload: filename=%s bytes=%d custom_prompt=%s",
            filename,
            len(image_bytes),
            "yes" if (prompt or "").strip() else "no",
        )

        preprocess_start_at = time.perf_counter()
        ocr_image_bytes, ocr_content_type, ocr_filename, preprocess_meta = prepare_image_for_ocr_pipeline(
            image_bytes,
            content_type,
            filename,
            enable_local_preprocess=settings.enable_local_preprocess,
        )
        preprocess_ms = int((time.perf_counter() - preprocess_start_at) * 1000)
        ocr_start_at = time.perf_counter()
        items, effective_prompt = ocr_service.extract_questions(
            ocr_image_bytes,
            ocr_content_type,
            ocr_filename,
            prompt=prompt,
        )
        ocr_ms = int((time.perf_counter() - ocr_start_at) * 1000)
        logger.info(
            "OCR-LLM simple completed: questions=%d preprocess_ms=%d ocr_ms=%d preprocessing_applied=%s",
            len(items),
            preprocess_ms,
            ocr_ms,
            bool(preprocess_meta.get("preprocessing_applied")),
        )
        response_prompt = effective_prompt
        logger.info("OCR simple response prompt=%r", response_prompt)
        payload = OcrExtractResponse(
            items=items,
            used_prompt=response_prompt,
            prompt=response_prompt,
        )
        return JSONResponse(content=payload.model_dump(mode="json", exclude_none=False))

    except RuntimeError as exc:
        logger.exception("OCR failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/api/ocr/diagram/crop", response_model=DiagramCropGenerateResponse)
async def generate_diagram_crop(payload: DiagramCropGenerateRequest, db: Session = Depends(get_db)):
    if not settings.enable_whatai_diagram_crop:
        return DiagramCropGenerateResponse()

    question_image_bytes, content_type = _load_asset_bytes(payload.question_image_url)
    result = diagram_llm_service.generate_diagram_crop(
        question_image_bytes,
        question_text=payload.question_text,
        content_type=content_type,
        trace_id=f"diagram-crop:item:{payload.item_id or 'unknown'}",
        db=db,
    )
    if not result:
        return DiagramCropGenerateResponse()

    storage = get_storage_service()
    diagram_llm_image_url = storage.upload_question_asset(
        result.image_bytes,
        payload.item_id or 0,
        90,
        suffix=".png",
    )
    return DiagramCropGenerateResponse(diagram_llm_image_url=diagram_llm_image_url)


@router.post("/api/ocr/diagram/svg", response_model=DiagramSvgGenerateResponse)
async def generate_diagram_svg(payload: DiagramSvgGenerateRequest, db: Session = Depends(get_db)):
    if not settings.enable_whatai_diagram_svg:
        return DiagramSvgGenerateResponse()

    diagram_seed_bytes = None
    if payload.diagram_image_url:
        try:
            diagram_seed_bytes, _ = _load_asset_bytes(payload.diagram_image_url)
        except HTTPException as exc:
            logger.warning(
                "SVG seed diagram load failed for item=%s: %s",
                payload.item_id,
                exc.detail,
            )
    if not diagram_seed_bytes and payload.question_image_url:
        try:
            diagram_seed_bytes, _ = _load_asset_bytes(payload.question_image_url)
        except HTTPException as exc:
            logger.warning(
                "SVG seed question load failed for item=%s: %s",
                payload.item_id,
                exc.detail,
            )

    diagram_svg = diagram_llm_service.generate_diagram_svg(
        payload.question_text,
        diagram_image_bytes=diagram_seed_bytes,
        trace_id=f"diagram-svg:item:{payload.item_id or 'unknown'}",
        db=db,
    )
    if not diagram_svg:
        return DiagramSvgGenerateResponse()

    storage = get_storage_service()
    diagram_svg_url = storage.upload_question_asset(
        diagram_svg.encode("utf-8"),
        payload.item_id or 0,
        91,
        suffix=".svg",
    )
    return DiagramSvgGenerateResponse(diagram_svg_url=diagram_svg_url)


@router.post("/api/ocr/analyze-question", response_model=QuestionAnalyzeResponse)
async def analyze_question(payload: QuestionAnalyzeRequest, db: Session = Depends(get_db)):
    """
    分析题目内容，智能推断学科、错题分类、错误原因和标题。

    独立的 LLM 调用，结合学生年级进行推断。
    """
    if not payload.question_text or not payload.question_text.strip():
        return QuestionAnalyzeResponse()

    result = question_analysis_service.analyze_question(
        payload.question_text,
        grade=payload.grade,
        db=db,
    )
    if not result:
        return QuestionAnalyzeResponse()

    return QuestionAnalyzeResponse(
        subject=result.get("subject"),
        category=result.get("category"),
        error_reason=result.get("error_reason"),
        title=result.get("title"),
    )
