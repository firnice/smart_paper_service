import logging
from fastapi import APIRouter, File, HTTPException, UploadFile, Depends
from sqlalchemy.orm import Session

from app.schemas.common import ImageBox
from app.schemas.ocr import OcrExtractResponse, OcrExtractResponseV2, OcrItemWithUrls
from app.services import ocr_service
from app.services.image_service import (
    crop_diagram_image,
    crop_image,
    get_image_size,
    has_meaningful_content,
    normalize_image_box_for_source,
    normalize_image_for_ocr,
)
from app.services.storage_service import get_storage_service
from app.db.session import get_db
from app.db.models.paper import Paper
from app.db.models.question import Question
from app.db.models.question_image import QuestionImage

router = APIRouter()
logger = logging.getLogger("uvicorn.error")


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

        # 0. Normalize image format for OCR (e.g. HEIC -> JPEG)
        ocr_image_bytes, ocr_content_type, ocr_filename = normalize_image_for_ocr(
            image_bytes,
            content_type,
            filename,
        )
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
        ocr_items = ocr_service.extract_questions(
            ocr_image_bytes,
            ocr_content_type,
            ocr_filename
        )
        logger.info("OCR extracted %d questions", len(ocr_items))

        # 4. 处理每个题目
        result_items = []
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
            image_urls = []
            next_index = 0

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

                    cropped_bytes, width, height = crop_diagram_image(
                        ocr_image_bytes,
                        refined_box.ymin,
                        refined_box.xmin,
                        refined_box.ymax,
                        refined_box.xmax,
                    )
                    if refined_applied and not has_meaningful_content(cropped_bytes):
                        logger.info(
                            "Refined diagram crop seems blank for q%s, fallback to initial image_box",
                            item.id,
                        )
                        refined_box = normalized_box
                        cropped_bytes, width, height = crop_diagram_image(
                            ocr_image_bytes,
                            refined_box.ymin,
                            refined_box.xmin,
                            refined_box.ymax,
                            refined_box.xmax,
                        )

                    # 上传裁剪后的图片
                    img_url = storage.upload_question_image(
                        cropped_bytes,
                        question.id,
                        next_index
                    )
                    next_index += 1
                    diagram_image_url = img_url

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
                    image_urls=image_urls,
                )
            )

        # 5. 更新 Paper 状态并提交
        paper.status = "processed"
        db.commit()

        logger.info(
            "OCR processing completed: paper_id=%d, questions=%d",
            paper.id,
            len(result_items)
        )

        return OcrExtractResponseV2(
            items=result_items,
            paper_id=paper.id
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

        ocr_image_bytes, ocr_content_type, ocr_filename = normalize_image_for_ocr(
            image_bytes,
            content_type,
            filename,
        )
        image_width, image_height = get_image_size(ocr_image_bytes)

        items = ocr_service.extract_questions(
            ocr_image_bytes,
            ocr_content_type,
            ocr_filename
        )
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
        return OcrExtractResponse(items=normalized_items)

    except RuntimeError as exc:
        logger.exception("OCR failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
