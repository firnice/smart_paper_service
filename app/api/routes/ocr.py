import base64
import binascii
import logging
import mimetypes
import time
from pathlib import Path
from urllib.parse import unquote_to_bytes, urlparse
from fastapi import APIRouter, File, HTTPException, UploadFile, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.common import ImageBox
from app.schemas.ocr import (
    DiagramCropGenerateRequest,
    DiagramCropGenerateResponse,
    DiagramSvgGenerateRequest,
    DiagramSvgGenerateResponse,
    OcrExtractResponse,
    OcrExtractResponseV2,
    OcrItemWithUrls,
    OcrPipelineMetrics,
)
from app.services import annotation_clean_service
from app.services import confidence_service
from app.services import diagram_llm_service
from app.services import ocr_service
from app.services import question_rebuild_service
from app.services.image_service import (
    crop_diagram_image_with_metadata,
    crop_image,
    get_image_size,
    has_meaningful_content,
    normalize_image_box_for_source,
    prepare_image_for_ocr_pipeline,
    should_use_annotation_saas_fallback,
)
from app.services.storage_service import get_storage_service
from app.db.session import get_db
from app.db.models.paper import Paper
from app.db.models.question import Question
from app.db.models.question_image import QuestionImage

router = APIRouter()
logger = logging.getLogger("uvicorn.error")


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


def _box_iou(a: ImageBox, b: ImageBox) -> float:
    inter_left = max(a.xmin, b.xmin)
    inter_top = max(a.ymin, b.ymin)
    inter_right = min(a.xmax, b.xmax)
    inter_bottom = min(a.ymax, b.ymax)
    inter_w = max(0, inter_right - inter_left)
    inter_h = max(0, inter_bottom - inter_top)
    inter_area = inter_w * inter_h
    if inter_area <= 0:
        return 0.0

    area_a = max(1, (a.xmax - a.xmin) * (a.ymax - a.ymin))
    area_b = max(1, (b.xmax - b.xmin) * (b.ymax - b.ymin))
    union_area = area_a + area_b - inter_area
    return inter_area / max(1, union_area)


def _expand_box_within(
    box: ImageBox,
    *,
    limit_top: int,
    limit_left: int,
    limit_bottom: int,
    limit_right: int,
    pad_x_ratio: float = 0.08,
    pad_y_ratio: float = 0.35,
    min_height: int = 0,
) -> ImageBox:
    w = max(1, box.xmax - box.xmin)
    h = max(1, box.ymax - box.ymin)
    pad_x = max(10, int(w * pad_x_ratio))
    pad_y = max(8, int(h * pad_y_ratio))

    left = max(limit_left, box.xmin - pad_x)
    right = min(limit_right, box.xmax + pad_x)
    top = max(limit_top, box.ymin - pad_y)
    bottom = min(limit_bottom, box.ymax + pad_y)

    if min_height > 0 and (bottom - top) < min_height:
        target = min(min_height, max(1, limit_bottom - limit_top))
        center = (top + bottom) // 2
        half = target // 2
        top = max(limit_top, center - half)
        bottom = min(limit_bottom, top + target)
        if bottom - top < target:
            top = max(limit_top, bottom - target)

    return ImageBox(ymin=top, xmin=left, ymax=bottom, xmax=right)


@router.post("/api/ocr/extract", response_model=OcrExtractResponseV2)
async def extract_questions(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    OCR 提取题目（完整流程）

    流程：
    1. 保存原始图片到存储
    2. 创建 Paper 记录
    3. OCR 识别题目和插图坐标
    4. 对每个题目：
       - 创建 Question 记录
       - 裁剪插图并保存
       - 创建 QuestionImage 记录
    5. 提交数据库事务
    6. 返回题目列表（包含插图 URL）
    """
    content_type = file.content_type or "image/png"
    filename = file.filename or "upload.png"

    try:
        # 读取上传的图片
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Empty upload.")

        logger.info(
            "OCR upload received filename=%s bytes=%d content_type=%s",
            filename,
            len(image_bytes),
            content_type,
        )

        preprocess_start_at = time.perf_counter()
        ocr_image_bytes, ocr_content_type, ocr_filename, preprocess_meta = prepare_image_for_ocr_pipeline(
            image_bytes,
            content_type,
            filename,
            enable_local_preprocess=settings.enable_local_preprocess,
        )
        preprocess_ms = int((time.perf_counter() - preprocess_start_at) * 1000)

        image_width, image_height = get_image_size(ocr_image_bytes)

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

        # 3. OCR 识别
        ocr_start_at = time.perf_counter()
        ocr_items = ocr_service.extract_questions(
            ocr_image_bytes,
            ocr_content_type,
            ocr_filename
        )
        ocr_ms = int((time.perf_counter() - ocr_start_at) * 1000)
        logger.info("OCR extracted %d questions", len(ocr_items))

        # 4. 处理每个题目
        result_items = []
        crop_start_at = time.perf_counter()
        clean_ms_total = 0
        clean_fallback_count = 0
        rebuild_ms_total = 0
        manual_refine_count = 0
        for item in ocr_items:
            normalized_question_box = normalize_image_box_for_source(
                item.question_box,
                image_width,
                image_height,
            )
            normalized_box = normalize_image_box_for_source(
                item.image_box,
                image_width,
                image_height,
            )
            has_image = bool(item.has_image or normalized_box)

            # 创建 Question 记录
            question = Question(
                paper_id=paper.id,
                question_no=item.id,
                text=item.text,
                has_image=has_image
            )
            db.add(question)
            db.flush()  # 获取 question.id

            # 裁剪并保存插图
            question_image_url = None
            diagram_image_url = None
            diagram_local_image_url = None
            diagram_llm_image_url = None
            diagram_svg_url = None
            image_urls = []
            next_index = 0
            clean_source = None
            clean_fallback = False
            clean_fallback_reason = None
            diagram_image_bytes = None
            question_snapshot_bytes = None

            if normalized_question_box:
                try:
                    question_bytes, q_width, q_height = crop_image(
                        ocr_image_bytes,
                        normalized_question_box.ymin,
                        normalized_question_box.xmin,
                        normalized_question_box.ymax,
                        normalized_question_box.xmax,
                    )
                    question_image_url = storage.upload_question_image(
                        question_bytes,
                        question.id,
                        next_index,
                    )
                    next_index += 1

                    db.add(
                        QuestionImage(
                            question_id=question.id,
                            image_url=question_image_url,
                            ymin=normalized_question_box.ymin,
                            xmin=normalized_question_box.xmin,
                            ymax=normalized_question_box.ymax,
                            xmax=normalized_question_box.xmax,
                            width=q_width,
                            height=q_height,
                        )
                    )
                    question_snapshot_bytes = question_bytes
                except Exception as e:
                    logger.exception(
                        "Failed to crop question snapshot for question %d: %s",
                        item.id,
                        str(e)
                    )

            if has_image and normalized_box:
                initial_box = normalized_box
                refined_box = normalized_box
                refined_applied = False
                try:
                    if normalized_question_box:
                        question_source_bytes, q_src_w, q_src_h = crop_image(
                            ocr_image_bytes,
                            normalized_question_box.ymin,
                            normalized_question_box.xmin,
                            normalized_question_box.ymax,
                            normalized_question_box.xmax,
                            max_size=None,
                        )
                        refined_local_box = None
                        try:
                            refined_local_box = ocr_service.refine_diagram_box(
                                question_source_bytes,
                                "image/png",
                                f"{ocr_filename}-q{item.id}-refine.png",
                            )
                        except Exception as refine_exc:
                            logger.warning(
                                "Refine diagram box failed for q%s, fallback to initial box: %s",
                                item.id,
                                str(refine_exc),
                            )
                        if refined_local_box:
                            refined_local_box = normalize_image_box_for_source(
                                refined_local_box,
                                q_src_w,
                                q_src_h,
                            )
                        if refined_local_box:
                            refined_candidate = ImageBox(
                                ymin=normalized_question_box.ymin + refined_local_box.ymin,
                                xmin=normalized_question_box.xmin + refined_local_box.xmin,
                                ymax=normalized_question_box.ymin + refined_local_box.ymax,
                                xmax=normalized_question_box.xmin + refined_local_box.xmax,
                            )
                            refined_abs_box = normalize_image_box_for_source(
                                refined_candidate,
                                image_width,
                                image_height,
                            )
                            if refined_abs_box:
                                refined_area = max(
                                    1,
                                    (refined_abs_box.ymax - refined_abs_box.ymin)
                                    * (refined_abs_box.xmax - refined_abs_box.xmin),
                                )
                                initial_area = max(
                                    1,
                                    (initial_box.ymax - initial_box.ymin)
                                    * (initial_box.xmax - initial_box.xmin),
                                )
                                question_area = max(
                                    1,
                                    (normalized_question_box.ymax - normalized_question_box.ymin)
                                    * (normalized_question_box.xmax - normalized_question_box.xmin),
                                )
                                refined_w = max(1, refined_abs_box.xmax - refined_abs_box.xmin)
                                refined_h = max(1, refined_abs_box.ymax - refined_abs_box.ymin)
                                refined_aspect = refined_w / refined_h
                                area_ratio_vs_initial = refined_area / initial_area
                                iou_vs_initial = _box_iou(initial_box, refined_abs_box)
                                initial_center_y = (initial_box.ymin + initial_box.ymax) / 2
                                refined_center_y = (refined_abs_box.ymin + refined_abs_box.ymax) / 2
                                center_shift = abs(refined_center_y - initial_center_y)
                                question_h = max(1, normalized_question_box.ymax - normalized_question_box.ymin)

                                # 精修框必须与初始框保持足够重叠，避免跑偏到手写区域。
                                if (
                                    refined_area >= int(question_area * 0.08)
                                    and refined_area <= int(question_area * 0.92)
                                    and 0.2 <= refined_aspect <= 6.0
                                    and 0.58 <= area_ratio_vs_initial <= 1.45
                                    and iou_vs_initial >= 0.42
                                    and center_shift <= question_h * 0.14
                                ):
                                    refined_box = refined_abs_box
                                    refined_applied = True
                                    logger.info(
                                        "Refined diagram box applied for q%s: (%d,%d,%d,%d) within question=%dx%d iou=%.3f ratio=%.3f",
                                        item.id,
                                        refined_box.ymin,
                                        refined_box.xmin,
                                        refined_box.ymax,
                                        refined_box.xmax,
                                        q_src_w,
                                        q_src_h,
                                        iou_vs_initial,
                                        area_ratio_vs_initial,
                                    )
                                else:
                                    logger.info(
                                        "Refined diagram box rejected for q%s area=%d question_area=%d aspect=%.2f iou=%.3f ratio=%.3f shift=%.1f",
                                        item.id,
                                        refined_area,
                                        question_area,
                                        refined_aspect,
                                        iou_vs_initial,
                                        area_ratio_vs_initial,
                                        center_shift,
                                    )

                    if not refined_applied:
                        if normalized_question_box:
                            q_h = max(1, normalized_question_box.ymax - normalized_question_box.ymin)
                            refined_box = _expand_box_within(
                                refined_box,
                                limit_top=normalized_question_box.ymin,
                                limit_left=normalized_question_box.xmin,
                                limit_bottom=normalized_question_box.ymax,
                                limit_right=normalized_question_box.xmax,
                                min_height=int(q_h * 0.38),
                            )
                        else:
                            refined_box = _expand_box_within(
                                refined_box,
                                limit_top=0,
                                limit_left=0,
                                limit_bottom=image_height,
                                limit_right=image_width,
                            )

                    clean_started_at = time.perf_counter()
                    cropped_bytes, width, height, clean_stats = crop_diagram_image_with_metadata(
                        ocr_image_bytes,
                        refined_box.ymin,
                        refined_box.xmin,
                        refined_box.ymax,
                        refined_box.xmax,
                    )
                    clean_source = "local_rule"
                    needs_saas_fallback, clean_fallback_reason = should_use_annotation_saas_fallback(clean_stats)
                    if refined_applied and not has_meaningful_content(cropped_bytes):
                        logger.info(
                            "Refined diagram crop seems blank for q%s, fallback to initial image_box",
                            item.id,
                        )
                        refined_box = normalized_box
                        cropped_bytes, width, height, clean_stats = crop_diagram_image_with_metadata(
                            ocr_image_bytes,
                            refined_box.ymin,
                            refined_box.xmin,
                            refined_box.ymax,
                            refined_box.xmax,
                        )
                        retry_needs_fallback, retry_reason = should_use_annotation_saas_fallback(clean_stats)
                        needs_saas_fallback = needs_saas_fallback or retry_needs_fallback
                        clean_fallback_reason = clean_fallback_reason or retry_reason or "refined_crop_blank"

                    if not has_meaningful_content(cropped_bytes):
                        needs_saas_fallback = True
                        clean_fallback_reason = clean_fallback_reason or "local_output_blank"

                    if needs_saas_fallback:
                        if annotation_clean_service.is_annotation_clean_fallback_enabled():
                            raw_crop_bytes, _, _ = crop_image(
                                ocr_image_bytes,
                                refined_box.ymin,
                                refined_box.xmin,
                                refined_box.ymax,
                                refined_box.xmax,
                                max_size=None,
                            )
                            saas_bytes = annotation_clean_service.clean_diagram_with_saas(
                                raw_crop_bytes,
                                content_type="image/png",
                                file_name=f"{ocr_filename}-q{item.id}-diagram.png",
                            )
                            if saas_bytes and has_meaningful_content(saas_bytes):
                                cropped_bytes = saas_bytes
                                width, height = get_image_size(saas_bytes)
                                clean_source = "saas_fallback"
                                clean_fallback = True
                                clean_fallback_count += 1
                                clean_fallback_reason = clean_fallback_reason or "local_clean_quality_low"
                            else:
                                clean_fallback_reason = (
                                    f"{clean_fallback_reason or 'local_clean_quality_low'};saas_failed"
                                )
                        else:
                            clean_fallback_reason = (
                                f"{clean_fallback_reason or 'local_clean_quality_low'};saas_disabled"
                            )

                    clean_ms_total += int((time.perf_counter() - clean_started_at) * 1000)

                    diagram_image_bytes = cropped_bytes
                    # 上传裁剪后的图片
                    img_url = storage.upload_question_image(
                        cropped_bytes,
                        question.id,
                        next_index
                    )
                    next_index += 1
                    diagram_image_url = img_url
                    diagram_local_image_url = img_url

                    # 创建 QuestionImage 记录
                    q_img = QuestionImage(
                        question_id=question.id,
                        image_url=img_url,
                        ymin=refined_box.ymin,
                        xmin=refined_box.xmin,
                        ymax=refined_box.ymax,
                        xmax=refined_box.xmax,
                        width=width,
                        height=height,
                    )
                    db.add(q_img)
                    image_urls.append(img_url)  # backward compatibility: diagram-only list
                    normalized_box = refined_box

                    logger.info(
                        "Cropped and saved image for question %d: %s",
                        question.id,
                        img_url
                    )

                except Exception as e:
                    logger.exception(
                        "Failed to crop image for question %d: %s",
                        item.id,
                        str(e)
                    )
                    # 不阻断流程，继续处理其他题目

            rebuild_started_at = time.perf_counter()
            rebuild_json = None
            if settings.enable_rebuild_json:
                rebuild_json = question_rebuild_service.rebuild_question_json(
                    item.text,
                    diagram_image_bytes=diagram_image_bytes,
                )
            rebuild_ms_total += int((time.perf_counter() - rebuild_started_at) * 1000)

            confidence_assessment = confidence_service.compute_rebuild_assessment(
                source_text=item.text,
                rebuild_json=rebuild_json,
                has_image=has_image,
                has_diagram_output=bool(diagram_image_url),
                clean_fallback_used=clean_fallback,
            )
            confidence = float(confidence_assessment.get("score", 0.0))
            status = "ok"
            if settings.force_manual_refine_on_low_conf and confidence < settings.rebuild_confidence_threshold:
                status = "need_manual_refine"
                manual_refine_count += 1

            # 构建响应项
            result_items.append(
                OcrItemWithUrls(
                    id=item.id,
                    text=item.text,
                    has_image=has_image,
                    question_box=normalized_question_box,
                    image_box=normalized_box,
                    question_image_url=question_image_url,
                    diagram_image_url=diagram_image_url,
                    diagram_local_image_url=diagram_local_image_url,
                    diagram_llm_image_url=diagram_llm_image_url,
                    diagram_svg_url=diagram_svg_url,
                    image_urls=image_urls,
                    clean_source=clean_source,
                    clean_fallback=clean_fallback,
                    clean_fallback_reason=clean_fallback_reason,
                    rebuild_json=rebuild_json,
                    confidence=confidence,
                    confidence_reasons=list(confidence_assessment.get("reasons", [])),
                    confidence_breakdown=confidence_assessment.get("breakdown"),
                    status=status,
                )
            )

        crop_ms = int((time.perf_counter() - crop_start_at) * 1000)
        pipeline_metrics = OcrPipelineMetrics(
            preprocess_ms=preprocess_ms,
            ocr_ms=ocr_ms,
            crop_ms=crop_ms,
            clean_ms=clean_ms_total,
            clean_fallback_count=clean_fallback_count,
            rebuild_ms=rebuild_ms_total,
            manual_refine_count=manual_refine_count,
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
            "OCR processing completed: paper_id=%d, questions=%d preprocess_ms=%d ocr_ms=%d crop_ms=%d clean_ms=%d rebuild_ms=%d clean_fallback_count=%d manual_refine_count=%d preprocessing_applied=%s",
            paper.id,
            len(result_items),
            pipeline_metrics.preprocess_ms,
            pipeline_metrics.ocr_ms,
            pipeline_metrics.crop_ms,
            pipeline_metrics.clean_ms,
            pipeline_metrics.rebuild_ms,
            pipeline_metrics.clean_fallback_count,
            pipeline_metrics.manual_refine_count,
            pipeline_metrics.preprocessing_applied,
        )

        return OcrExtractResponseV2(
            items=result_items,
            paper_id=paper.id,
            pipeline_metrics=pipeline_metrics,
        )

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


@router.post("/api/ocr/extract/simple", response_model=OcrExtractResponse)
async def extract_questions_simple(file: UploadFile = File(...)):
    """
    OCR 提取题目（简单版本，不入库）

    仅执行 OCR 识别，不保存到数据库，用于快速测试。
    """
    content_type = file.content_type or "image/png"
    filename = file.filename or "upload.png"
    try:
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Empty upload.")

        logger.info(
            "OCR simple upload: filename=%s bytes=%d",
            filename,
            len(image_bytes),
        )

        preprocess_start_at = time.perf_counter()
        ocr_image_bytes, ocr_content_type, ocr_filename, preprocess_meta = prepare_image_for_ocr_pipeline(
            image_bytes,
            content_type,
            filename,
            enable_local_preprocess=settings.enable_local_preprocess,
        )
        preprocess_ms = int((time.perf_counter() - preprocess_start_at) * 1000)
        image_width, image_height = get_image_size(ocr_image_bytes)

        ocr_start_at = time.perf_counter()
        items = ocr_service.extract_questions(
            ocr_image_bytes,
            ocr_content_type,
            ocr_filename
        )
        ocr_ms = int((time.perf_counter() - ocr_start_at) * 1000)
        normalized_items = []
        for item in items:
            normalized_question_box = normalize_image_box_for_source(
                item.question_box,
                image_width,
                image_height,
            )
            normalized_box = normalize_image_box_for_source(
                item.image_box,
                image_width,
                image_height,
            )
            normalized_items.append(
                item.model_copy(
                    update={
                        "has_image": bool(item.has_image or normalized_box),
                        "question_box": normalized_question_box,
                        "image_box": normalized_box,
                    }
                )
            )
        logger.info(
            "OCR simple completed: questions=%d preprocess_ms=%d ocr_ms=%d preprocessing_applied=%s",
            len(normalized_items),
            preprocess_ms,
            ocr_ms,
            bool(preprocess_meta.get("preprocessing_applied")),
        )
        return OcrExtractResponse(items=normalized_items)

    except RuntimeError as exc:
        logger.exception("OCR failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/api/ocr/diagram/crop", response_model=DiagramCropGenerateResponse)
async def generate_diagram_crop(payload: DiagramCropGenerateRequest):
    if not settings.enable_whatai_diagram_crop:
        return DiagramCropGenerateResponse()

    question_image_bytes, content_type = _load_asset_bytes(payload.question_image_url)
    result = diagram_llm_service.generate_diagram_crop(
        question_image_bytes,
        question_text=payload.question_text,
        content_type=content_type,
        trace_id=f"diagram-crop:item:{payload.item_id or 'unknown'}",
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
async def generate_diagram_svg(payload: DiagramSvgGenerateRequest):
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
