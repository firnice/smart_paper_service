from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models.export import Export
from app.db.session import get_db
from app.schemas.export import ExportRequest, ExportResponse
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
