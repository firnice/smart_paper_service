from app.schemas.common import ImageBox
from app.schemas.ocr import OcrItem


def extract_questions(file_name: str) -> list[OcrItem]:
    """Stub OCR extraction until the real model pipeline is wired."""
    return [
        OcrItem(
            id=1,
            text="小明买了5支铅笔，每支2元，一共多少钱？",
            has_image=False,
        ),
        OcrItem(
            id=2,
            text="看图写出角的度数。",
            has_image=True,
            image_box=ImageBox(ymin=120, xmin=80, ymax=320, xmax=360),
        ),
    ]
