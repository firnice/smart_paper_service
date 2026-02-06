import logging
from fastapi import APIRouter, File, HTTPException, UploadFile, Depends
from sqlalchemy.orm import Session

from app.schemas.ocr import OcrExtractResponse, OcrExtractResponseV2, OcrItemWithUrls
from app.services import ocr_service
from app.services.image_service import crop_image
from app.services.storage_service import get_storage_service
from app.db.session import get_db
from app.db.models.paper import Paper
from app.db.models.question import Question
from app.db.models.question_image import QuestionImage

router = APIRouter()
logger = logging.getLogger("uvicorn.error")


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

    try:
        # 读取上传的图片
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Empty upload.")

        logger.info(
            "OCR upload received filename=%s bytes=%d content_type=%s",
            file.filename or "upload",
            len(image_bytes),
            content_type,
        )

        storage = get_storage_service()

        # 1. 保存原始图片到存储
        paper_url = storage.upload_paper_image(image_bytes, file.filename or "upload.png")
        logger.info("Saved original paper image: %s", paper_url)

        # 2. 创建 Paper 记录
        paper = Paper(
            title=file.filename or "Untitled",
            original_image_url=paper_url,
            status="processing"
        )
        db.add(paper)
        db.flush()  # 获取 paper.id
        logger.info("Created Paper record: id=%d", paper.id)

        # 3. OCR 识别
        ocr_items = ocr_service.extract_questions(
            image_bytes,
            content_type,
            file.filename or "upload"
        )
        logger.info("OCR extracted %d questions", len(ocr_items))

        # 4. 处理每个题目
        result_items = []
        for item in ocr_items:
            # 创建 Question 记录
            question = Question(
                paper_id=paper.id,
                question_no=item.id,
                text=item.text,
                has_image=item.has_image
            )
            db.add(question)
            db.flush()  # 获取 question.id

            # 裁剪并保存插图
            image_urls = []
            if item.has_image and item.image_box:
                try:
                    cropped_bytes, width, height = crop_image(
                        image_bytes,
                        item.image_box.ymin,
                        item.image_box.xmin,
                        item.image_box.ymax,
                        item.image_box.xmax,
                    )

                    # 上传裁剪后的图片
                    img_url = storage.upload_question_image(
                        cropped_bytes,
                        question.id,
                        0
                    )

                    # 创建 QuestionImage 记录
                    q_img = QuestionImage(
                        question_id=question.id,
                        image_url=img_url,
                        ymin=item.image_box.ymin,
                        xmin=item.image_box.xmin,
                        ymax=item.image_box.ymax,
                        xmax=item.image_box.xmax,
                        width=width,
                        height=height,
                    )
                    db.add(q_img)
                    image_urls.append(img_url)

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
                    has_image=item.has_image,
                    image_box=item.image_box,
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
        raise HTTPException(status_code=502, detail="OCR service unavailable.") from exc
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
    try:
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Empty upload.")

        logger.info(
            "OCR simple upload: filename=%s bytes=%d",
            file.filename or "upload",
            len(image_bytes),
        )

        items = ocr_service.extract_questions(
            image_bytes,
            content_type,
            file.filename or "upload"
        )
        return OcrExtractResponse(items=items)

    except RuntimeError as exc:
        logger.exception("OCR failed")
        raise HTTPException(status_code=502, detail="OCR service unavailable.") from exc
