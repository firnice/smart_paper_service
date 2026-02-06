import uuid
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("uvicorn.error")


class LocalStorageService:
    """本地文件存储服务（MVP 阶段）"""

    def __init__(self, base_dir: str, base_url: str):
        """
        初始化本地存储服务

        Args:
            base_dir: 存储根目录
            base_url: 访问基础 URL（用于生成可访问的 URL）
        """
        self.base_dir = Path(base_dir)
        self.base_url = base_url.rstrip("/")

        # 创建必要的子目录
        for subdir in ["papers", "questions", "exports"]:
            (self.base_dir / subdir).mkdir(parents=True, exist_ok=True)

        logger.info(
            "LocalStorageService initialized: base_dir=%s, base_url=%s",
            self.base_dir,
            self.base_url
        )

    def upload_paper_image(self, file_bytes: bytes, filename: str) -> str:
        """
        上传原始试卷图片

        Args:
            file_bytes: 图片字节流
            filename: 原始文件名

        Returns:
            可访问的图片 URL
        """
        file_id = str(uuid.uuid4())
        ext = Path(filename).suffix or ".png"
        new_filename = f"{file_id}{ext}"
        file_path = self.base_dir / "papers" / new_filename

        file_path.write_bytes(file_bytes)
        logger.info("Saved paper image: %s (%d bytes)", new_filename, len(file_bytes))

        return f"{self.base_url}/papers/{new_filename}"

    def upload_question_image(
        self,
        file_bytes: bytes,
        question_id: int,
        index: int = 0
    ) -> str:
        """
        上传题目插图

        Args:
            file_bytes: 图片字节流
            question_id: 题目 ID
            index: 插图序号（一个题目可能有多个插图）

        Returns:
            可访问的图片 URL
        """
        filename = f"q{question_id}_{index}_{uuid.uuid4().hex[:8]}.png"
        file_path = self.base_dir / "questions" / filename

        file_path.write_bytes(file_bytes)
        logger.info("Saved question image: %s (%d bytes)", filename, len(file_bytes))

        return f"{self.base_url}/questions/{filename}"

    def upload_export(self, file_bytes: bytes, job_id: str, format: str = "pdf") -> str:
        """
        上传导出文件

        Args:
            file_bytes: 文件字节流
            job_id: 导出任务 ID
            format: 文件格式（pdf, docx 等）

        Returns:
            可访问的文件 URL
        """
        filename = f"{job_id}.{format}"
        file_path = self.base_dir / "exports" / filename

        file_path.write_bytes(file_bytes)
        logger.info("Saved export file: %s (%d bytes)", filename, len(file_bytes))

        return f"{self.base_url}/exports/{filename}"


# 全局存储服务实例（单例模式）
_storage: Optional[LocalStorageService] = None


def get_storage_service() -> LocalStorageService:
    """获取存储服务实例（全局单例）"""
    global _storage
    if _storage is None:
        from app.core.config import settings
        _storage = LocalStorageService(
            base_dir=settings.storage_base_dir,
            base_url=settings.storage_base_url,
        )
    return _storage


# 保留旧的 upload_asset 函数以保持向后兼容（已弃用）
def upload_asset(filename: str, content_type: str) -> str:
    """
    Deprecated: Use get_storage_service() instead.
    Stub asset uploader. Replace with OSS/S3 integration.
    """
    return f"https://assets.local/{filename}"
