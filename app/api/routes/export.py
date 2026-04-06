from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models.export import Export
from app.db.session import get_db
from app.schemas.export import (
    ExportRequest,
    ExportResponse,
    PrintPackExportRequest,
    PrintPackExportResponse,
)
from app.services import export_service

router = APIRouter()


@router.post("/api/export", response_model=ExportResponse)
def create_export_task(payload: ExportRequest, db: Session = Depends(get_db)):
    """
    创建导出任务（同步生成 PDF）

    兼容两种模式：
    1. 旧版单题/变式导出
    2. 新版多题打印重做包导出
    """
    response = export_service.create_export(
        title=payload.title,
        original_text=payload.original_text,
        variants=payload.variants,
        include_images=payload.include_images,
        mode=payload.mode,
        question_items=payload.question_items,
        hide_answers=payload.hide_answers,
    )

    try:
        export_record = Export(
            job_id=response.job_id,
            title=payload.title,
            original_text=payload.original_text or "",
            variants_json=payload.variants,
            include_images=payload.include_images,
            format="pdf",
            status=response.status,
            download_url=response.download_url,
            error_message=None if response.status == "completed" else "Export failed",
        )
        db.add(export_record)
        db.commit()
        db.refresh(export_record)
    except Exception:
        db.rollback()

    return response


@router.get("/api/export/{job_id}", response_model=ExportResponse)
def get_export_status(job_id: str, db: Session = Depends(get_db)):
    export_record = db.query(Export).filter(Export.job_id == job_id).first()

    if not export_record:
        raise HTTPException(status_code=404, detail="Export job not found")

    return ExportResponse(
        job_id=export_record.job_id,
        status=export_record.status,
        download_url=export_record.download_url,
    )


@router.post("/api/print-pack/export", response_model=PrintPackExportResponse)
def create_print_pack_export(payload: PrintPackExportRequest, db: Session = Depends(get_db)):
    response = export_service.create_print_pack_export(
        title=payload.title,
        paper_meta=payload.paper_meta,
        items=payload.items,
        answer_mode=payload.answer_mode,
    )

    export_record = Export(
        job_id=response.job_id,
        title=payload.title,
        original_text="",
        variants_json=[item.model_dump() for item in payload.items],
        include_images=any(bool((item.image_url or "").strip()) for item in payload.items),
        format="pdf",
        status=response.status,
        download_url=response.download_url,
        error_message=None if response.status == "completed" else "Print-pack export failed",
    )
    db.add(export_record)
    try:
        db.commit()
        db.refresh(export_record)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist print-pack export record",
        ) from exc

    return PrintPackExportResponse(
        id=export_record.id,
        status=response.status,
        download_url=response.download_url,
    )
