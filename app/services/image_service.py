from io import BytesIO
from typing import Optional
from PIL import Image
import logging

logger = logging.getLogger("uvicorn.error")


def crop_image(
    image_bytes: bytes,
    ymin: int,
    xmin: int,
    ymax: int,
    xmax: int,
    max_size: Optional[tuple[int, int]] = (800, 800)
) -> tuple[bytes, int, int]:
    """
    裁剪图片并返回裁剪后的字节流。

    Args:
        image_bytes: 原始图片字节流
        ymin, xmin, ymax, xmax: 裁剪坐标（原始图片坐标系）
        max_size: 最大尺寸限制（宽，高），None 表示不限制

    Returns:
        (cropped_bytes, width, height): 裁剪后的图片字节流和尺寸

    Raises:
        ValueError: 坐标无效
        RuntimeError: 图片处理失败
    """
    try:
        img = Image.open(BytesIO(image_bytes))
        width, height = img.size

        # 坐标校验（防止越界）
        ymin = max(0, min(ymin, height))
        xmin = max(0, min(xmin, width))
        ymax = max(ymin, min(ymax, height))
        xmax = max(xmin, min(xmax, width))

        # 检查裁剪区域是否有效
        if ymax <= ymin or xmax <= xmin:
            logger.error(
                "Invalid crop box: (%d,%d,%d,%d) for image size (%d,%d)",
                ymin, xmin, ymax, xmax, width, height
            )
            raise ValueError("Invalid crop coordinates")

        # PIL 使用 (left, upper, right, lower) = (xmin, ymin, xmax, ymax)
        cropped = img.crop((xmin, ymin, xmax, ymax))

        # 可选：缩放以节省存储空间
        if max_size:
            cropped.thumbnail(max_size, Image.Resampling.LANCZOS)

        # 转换为 bytes
        buffer = BytesIO()
        cropped.save(buffer, format="PNG")
        buffer.seek(0)

        logger.info(
            "Cropped image: (%d,%d,%d,%d) -> %dx%d",
            ymin, xmin, ymax, xmax,
            cropped.width, cropped.height
        )

        return buffer.read(), cropped.width, cropped.height

    except ValueError:
        raise
    except Exception as e:
        logger.exception("Image crop failed")
        raise RuntimeError(f"Image crop failed: {str(e)}") from e
