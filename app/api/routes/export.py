from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.schemas.export import ExportRequest, ExportResponse
from app.services import export_service
from app.db.session import get_db
from app.db.models.export import Export

router = APIRouter()


@router.post("/api/export", response_model=ExportResponse)
def create_export_task(
    payload: ExportRequest,
    db: Session = Depends(get_db)
):
    """
    创建导出任务（同步生成 PDF）

    流程：
    1. 调用导出服务生成 PDF
    2. 保存导出记录到数据库
    3. 返回下载 URL
    """
    # 1. 生成导出文件
    response = export_service.create_export(
        title=payload.title,
        original_text=payload.original_text,
        variants=payload.variants,
        include_images=payload.include_images,
    )

    # 2. 保存导出记录到数据库
    try:
        export_record = Export(
            job_id=response.job_id,
            title=payload.title,
            original_text=payload.original_text,
            variants_json=payload.variants,
            include_images=payload.include_images,
            format="pdf",
            status=response.status,
            download_url=response.download_url,
            error_message=None if response.status == "completed" else "Export failed"
        )
        db.add(export_record)
        db.commit()
        db.refresh(export_record)

    except Exception as e:
        db.rollback()
        # 即使数据库保存失败，也返回导出结果
        # 因为文件已经生成并存储
        pass

    return response


@router.get("/api/export/{job_id}", response_model=ExportResponse)
def get_export_status(job_id: str, db: Session = Depends(get_db)):
    """
    查询导出任务状态

    Args:
        job_id: 导出任务 ID

    Returns:
        导出任务状态和下载 URL
    """
    export_record = db.query(Export).filter(Export.job_id == job_id).first()

    if not export_record:
        raise HTTPException(status_code=404, detail="Export job not found")

    return ExportResponse(
        job_id=export_record.job_id,
        status=export_record.status,
        download_url=export_record.download_url,
    )
