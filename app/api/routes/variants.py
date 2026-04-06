from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.logger import logger
from app.db.models.wrong_question import WrongQuestion
from app.db.models.subject import Subject
from app.db.session import get_db
from app.schemas.variants import (
    VariantItemResponse,
    VariantSourceQuestionResponse,
    VariantsForQuestionRequest,
    VariantsForQuestionResponse,
    VariantsRequest,
    VariantsResponse,
)
from app.services import variant_service

router = APIRouter()


@router.post("/api/variants/generate", response_model=VariantsResponse)
def generate_variants(payload: VariantsRequest, db: Session = Depends(get_db)):
    try:
        items = variant_service.generate_variants(
            payload.source_text,
            payload.count,
            grade=payload.grade,
            subject=payload.subject,
            db=db,
        )
    except RuntimeError as exc:
        logger.exception("Variants generation failed")
        raise HTTPException(status_code=502, detail="LLM service unavailable.") from exc
    return VariantsResponse(items=items)


@router.post("/api/variants/generate-for-question", response_model=VariantsForQuestionResponse)
def generate_variants_for_question(
    payload: VariantsForQuestionRequest,
    db: Session = Depends(get_db),
):
    # 从 wrong_questions 表获取题目信息
    wq = db.query(WrongQuestion).filter(WrongQuestion.id == payload.wrong_question_id).first()
    if not wq:
        raise HTTPException(status_code=404, detail="Wrong question not found")

    # 获取学科名称
    subject_name = None
    if wq.subject_id:
        subject = db.query(Subject).filter(Subject.id == wq.subject_id).first()
        if subject:
            subject_name = subject.name

    # svg 字段优先；历史数据中 svg URL 存在 image_url（.svg 结尾）
    source_svg = wq.svg or (wq.image_url if (wq.image_url or "").endswith(".svg") else None)

    try:
        items, used_prompt = variant_service.generate_variants_for_question(
            source_text=wq.content,
            count=payload.count,
            grade=wq.grade,
            subject=subject_name,
            prompt=payload.prompt,
            source_svg=source_svg,
            db=db,
        )
    except RuntimeError as exc:
        logger.exception("Variants for question generation failed")
        raise HTTPException(status_code=502, detail="LLM service unavailable.") from exc

    return VariantsForQuestionResponse(
        source_question_id=payload.wrong_question_id,
        used_prompt=used_prompt,
        source_question=VariantSourceQuestionResponse(
            id=wq.id,
            text=wq.content,
            image_url=wq.image_url,
            reference_answer=wq.reference_answer,
            analysis=wq.analysis,
            svg=source_svg,
        ),
        items=[
            VariantItemResponse(
                id=f"var_{index:03d}",
                text=item.text,
                answer=item.answer,
                hint=item.hint,
                svg=item.svg,
            )
            for index, item in enumerate(items, start=1)
        ],
    )
