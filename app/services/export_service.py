from __future__ import annotations

from pathlib import Path
from io import BytesIO
from typing import Optional
from urllib.parse import urlparse, unquote
from uuid import uuid4
import mimetypes

from reportlab.lib.utils import ImageReader

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Table,
    TableStyle,
    KeepTogether,
    Image,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

from app.core.logger import logger

# Register built-in CID fonts for Chinese character support
pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
_FONT_NORMAL = "STSong-Light"
_FONT_BOLD = "STSong-Light"
from app.schemas.export import ExportQuestionItem, ExportResponse, PrintPackItem, PrintPackPaperMeta


def _resolve_local_image_bytes(image_url: Optional[str]) -> Optional[bytes]:
    if not image_url:
        return None
    value = str(image_url).strip()
    if not value:
        return None
    if value.startswith("data:"):
        header, _, data = value.partition(",")
        if not data:
            return None
        import base64
        from urllib.parse import unquote_to_bytes
        try:
            if ";base64" in header:
                return base64.b64decode(data)
            return unquote_to_bytes(data)
        except Exception:
            return None

    parsed = urlparse(value)
    path = unquote(parsed.path or "")
    if not path:
        return None

    static_marker = "/static/"
    if static_marker not in path:
        return None

    relative_path = path.split(static_marker, 1)[1].lstrip("/")
    from app.core.config import settings
    storage_root = Path(settings.storage_base_dir).resolve()
    file_path = (storage_root / relative_path).resolve()
    try:
        file_path.relative_to(storage_root)
    except ValueError:
        return None
    if not file_path.is_file():
        return None
    return file_path.read_bytes()


def _svg_bytes_to_png(svg_bytes: bytes) -> Optional[bytes]:
    """Convert SVG bytes to PNG bytes via cairosvg, with Chinese font fallback."""
    try:
        import cairosvg

        # Replace generic font families with a system font that supports Chinese.
        # cairosvg uses fonttools/pango for font lookup; on macOS sans-serif often
        # resolves to a Latin-only font. We substitute explicitly.
        _CHINESE_FONT = "STHeiti"
        svg_text = svg_bytes.decode("utf-8", errors="replace")
        import re as _re
        svg_text = _re.sub(
            r'font-family\s*=\s*["\']?(sans-serif|serif|monospace|system-ui)["\']?',
            f'font-family="{_CHINESE_FONT}"',
            svg_text,
        )
        # Also handle CSS style blocks: font-family: sans-serif
        svg_text = _re.sub(
            r'font-family\s*:\s*(sans-serif|serif|monospace|system-ui)',
            f'font-family: {_CHINESE_FONT}',
            svg_text,
        )
        return cairosvg.svg2png(bytestring=svg_text.encode("utf-8"))
    except Exception as exc:
        logger.warning("SVG to PNG conversion failed: %s", exc)
        return None


def _build_question_image(image_url: Optional[str], max_width: float, max_height: float):
    image_bytes = _resolve_local_image_bytes(image_url)
    if not image_bytes:
        return None
    # SVG needs to be converted to PNG for ReportLab
    stripped = image_bytes.lstrip()
    is_svg = stripped.startswith(b"<svg") or stripped.startswith(b"<?xml") or b"<svg" in stripped[:512]
    if is_svg:
        png_bytes = _svg_bytes_to_png(image_bytes)
        if not png_bytes:
            return None
        image_bytes = png_bytes
    try:
        image = Image(BytesIO(image_bytes))
        image._restrictSize(max_width, max_height)
        return image
    except Exception:
        logger.warning("Skip unsupported export image: %s", str(image_url)[:200])
        return None


def _base_doc_and_styles():
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=8,
        spaceBefore=4,
        fontName=_FONT_BOLD,
        textColor=colors.HexColor("#1a1a1a"),
    )
    section_title_style = ParagraphStyle(
        "SectionTitle",
        parent=styles["Heading2"],
        fontSize=13,
        alignment=TA_LEFT,
        spaceAfter=8,
        spaceBefore=10,
        fontName=_FONT_BOLD,
        textColor=colors.HexColor("#333333"),
        borderPadding=(3, 8, 3, 8),
        backColor=colors.HexColor("#f0f0f0"),
    )
    question_number_style = ParagraphStyle(
        "QuestionNumber",
        parent=styles["BodyText"],
        fontSize=12,
        fontName=_FONT_BOLD,
        textColor=colors.HexColor("#0066cc"),
        spaceAfter=4,
    )
    question_content_style = ParagraphStyle(
        "QuestionContent",
        parent=styles["BodyText"],
        fontSize=11,
        fontName=_FONT_NORMAL,
        alignment=TA_JUSTIFY,
        leading=17,
        leftIndent=12,
        spaceAfter=6,
    )
    answer_space_style = ParagraphStyle(
        "AnswerSpace",
        parent=styles["BodyText"],
        fontSize=10,
        fontName=_FONT_NORMAL,
        textColor=colors.HexColor("#999999"),
        leftIndent=12,
        spaceAfter=4,
    )
    footer_style = ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontSize=9,
        fontName=_FONT_NORMAL,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#999999"),
    )
    meta_style = ParagraphStyle(
        "Meta",
        parent=styles["BodyText"],
        fontSize=10,
        fontName=_FONT_NORMAL,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#4d4d4d"),
        spaceAfter=6,
    )
    answer_style = ParagraphStyle(
        "Answer",
        parent=styles["BodyText"],
        fontSize=10,
        fontName=_FONT_NORMAL,
        alignment=TA_LEFT,
        leading=15,
        leftIndent=12,
        textColor=colors.HexColor("#1f5f3f"),
        spaceAfter=6,
    )

    return buffer, doc, {
        "title": title_style,
        "section": section_title_style,
        "number": question_number_style,
        "content": question_content_style,
        "answer_space": answer_space_style,
        "footer": footer_style,
        "meta": meta_style,
        "answer": answer_style,
    }


def _add_answer_lines(story, doc, count=3):
    for _ in range(count):
        line = Table([["_" * 80]], colWidths=[doc.width])
        line.setStyle(
            TableStyle([
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#dddddd")),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
            ])
        )
        story.append(line)
        story.append(Spacer(1, 0.15 * cm))


def _question_table(text: str, doc, content_style, background="#fafafa", border="#cccccc"):
    formatted = (text or "").replace("\n", "<br/>")
    table = Table([[Paragraph(formatted, content_style)]], colWidths=[doc.width])
    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(background)),
            ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor(border)),
            ("TOPPADDING", (0, 0), (-1, -1), 15),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 15),
            ("LEFTPADDING", (0, 0), (-1, -1), 15),
            ("RIGHTPADDING", (0, 0), (-1, -1), 15),
        ])
    )
    return table


def _build_print_pack_meta(paper_meta: PrintPackPaperMeta) -> str:
    parts = [
        f"学生：{paper_meta.student_name or ''}",
        f"班级：{paper_meta.class_name or ''}",
        f"日期：{paper_meta.date or ''}",
    ]
    return "　　".join(parts)


def _build_answer_text(answer: Optional[str]) -> str:
    value = (answer or "").strip()
    return value or "暂无参考答案"


def _generate_pdf(
    title: str,
    original_text: str,
    variants: list[str],
    include_images: bool = False,
) -> bytes:
    buffer, doc, styles = _base_doc_and_styles()
    story = []

    story.append(Paragraph(title, styles["title"]))
    story.append(Spacer(1, 0.5 * cm))

    line_table = Table([[""]], colWidths=[doc.width])
    line_table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 2, colors.HexColor("#0066cc"))]))
    story.append(line_table)
    story.append(Spacer(1, 1 * cm))

    story.append(Paragraph("原题", styles["section"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(_question_table(original_text, doc, styles["content"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("【答题区域】", styles["answer_space"]))
    _add_answer_lines(story, doc)
    story.append(Spacer(1, 1 * cm))

    if variants:
        story.append(PageBreak())
        story.append(Paragraph("变式题（举一反三）", styles["section"]))
        story.append(Spacer(1, 0.5 * cm))
        for i, variant in enumerate(variants, 1):
            question_elements = [Paragraph(f"第 {i} 题", styles["number"])]
            question_elements.append(
                _question_table(variant, doc, styles["content"], background="#f8f9ff", border="#b3c6ff")
            )
            question_elements.append(Spacer(1, 0.3 * cm))
            question_elements.append(Paragraph("【答题区域】", styles["answer_space"]))
            _add_answer_lines(question_elements, doc)
            question_elements.append(Spacer(1, 1 * cm))
            if i < len(variants):
                divider = Table([[""]], colWidths=[doc.width])
                divider.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor("#e0e0e0"))]))
                question_elements.append(divider)
                question_elements.append(Spacer(1, 1 * cm))
            story.append(KeepTogether(question_elements))

    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph("—— 智能错题本练习卷 ——", styles["footer"]))
    doc.build(story)
    buffer.seek(0)
    return buffer.read()


def _generate_practice_sheet_pdf(
    title: str,
    question_items: list[ExportQuestionItem],
    hide_answers: bool = True,
) -> bytes:
    buffer, doc, styles = _base_doc_and_styles()
    story = []

    story.append(Paragraph(title, styles["title"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("打印重做包（线下重做优先）", styles["section"]))
    story.append(Spacer(1, 0.4 * cm))

    for index, item in enumerate(question_items, 1):
        block = []
        title_line = item.title or f"错题 {index}"
        meta_parts = [part for part in [item.subject, item.category] if part]
        if meta_parts:
            title_line += f"（{' / '.join(meta_parts)}）"
        block.append(Paragraph(f"第 {index} 题 · {title_line}", styles["number"]))
        question_image = _build_question_image(item.image_url, doc.width, 7 * cm)
        if question_image is not None:
            block.append(question_image)
            block.append(Spacer(1, 0.25 * cm))
        block.append(_question_table(item.content, doc, styles["content"]))
        block.append(Spacer(1, 0.2 * cm))
        if hide_answers:
            block.append(Paragraph("【作答区】", styles["answer_space"]))
            _add_answer_lines(block, doc, count=5)
        if index < len(question_items):
            block.append(Spacer(1, 0.5 * cm))
            divider = Table([[""]], colWidths=[doc.width])
            divider.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor("#e0e0e0"))]))
            block.append(divider)
            block.append(Spacer(1, 0.8 * cm))
        story.append(KeepTogether(block))

    story.append(Spacer(1, 0.8 * cm))
    story.append(Paragraph("—— 智能错题本打印重做包 ——", styles["footer"]))
    doc.build(story)
    buffer.seek(0)
    return buffer.read()


def _generate_print_pack_pdf(
    title: str,
    paper_meta: PrintPackPaperMeta,
    items: list[PrintPackItem],
    answer_mode: str,
) -> bytes:
    buffer, doc, styles = _base_doc_and_styles()
    story = []
    sorted_items = [item for _, item in sorted(enumerate(items), key=lambda pair: (pair[1].order, pair[0]))]

    story.append(Paragraph(title, styles["title"]))
    story.append(Paragraph(_build_print_pack_meta(paper_meta), styles["meta"]))
    story.append(Spacer(1, 0.4 * cm))

    for index, item in enumerate(sorted_items, 1):
        source_label = "原题" if item.type == "orig" else "AI 同类题"
        question_image = _build_question_image(item.image_url, doc.width, 5 * cm)

        # 题号行与图片（或题号行与题文）保持在一起，避免题号孤悬
        header_block = [Paragraph(f"第 {index} 题 · {source_label}", styles["number"])]
        if question_image is not None:
            header_block.append(question_image)
            header_block.append(Spacer(1, 0.15 * cm))
        story.append(KeepTogether(header_block))

        # 题文 + 答案/作答区单独添加，允许跨页
        story.append(_question_table(item.text, doc, styles["content"]))
        story.append(Spacer(1, 0.15 * cm))

        if answer_mode == "inline":
            story.append(Paragraph(f"参考答案：{_build_answer_text(item.answer)}", styles["answer"]))
        else:
            story.append(Paragraph("【作答区】", styles["answer_space"]))
            _add_answer_lines(story, doc, count=3)

        if index < len(sorted_items):
            story.append(Spacer(1, 0.3 * cm))
            divider = Table([[""]], colWidths=[doc.width])
            divider.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e0e0"))]))
            story.append(divider)
            story.append(Spacer(1, 0.3 * cm))

    if answer_mode == "sheet":
        items_with_answer = [item for item in sorted_items if (item.answer or "").strip()]
        if items_with_answer:
            story.append(PageBreak())
            story.append(Paragraph("参考答案", styles["section"]))
            story.append(Spacer(1, 0.4 * cm))
            for index, item in enumerate(sorted_items, 1):
                if not (item.answer or "").strip():
                    continue
                story.append(
                    Paragraph(f"第 {index} 题：{_build_answer_text(item.answer)}", styles["answer"])
                )

    story.append(Spacer(1, 0.8 * cm))
    story.append(Paragraph("—— 智能错题本打印重做包 ——", styles["footer"]))
    doc.build(story)
    buffer.seek(0)
    return buffer.read()


def create_export(
    title: str,
    original_text: Optional[str],
    variants: list[str],
    include_images: bool,
    mode: str = "single",
    question_items: Optional[list[ExportQuestionItem]] = None,
    hide_answers: bool = True,
) -> ExportResponse:
    from app.services.storage_service import get_storage_service

    job_id = str(uuid4())
    question_items = question_items or []

    try:
        if question_items:
            pdf_bytes = _generate_practice_sheet_pdf(title, question_items, hide_answers=hide_answers)
        else:
            pdf_bytes = _generate_pdf(title, original_text or "", variants, include_images)

        storage = get_storage_service()
        download_url = storage.upload_export(pdf_bytes, job_id, format="pdf")

        logger.info(
            "Export completed: job_id=%s mode=%s questions=%d url=%s",
            job_id,
            mode,
            len(question_items),
            download_url,
        )

        return ExportResponse(job_id=job_id, status="completed", download_url=download_url)
    except Exception:
        logger.exception("Export failed: job_id=%s mode=%s", job_id, mode)
        return ExportResponse(job_id=job_id, status="failed", download_url=None)


def create_print_pack_export(
    title: str,
    paper_meta: PrintPackPaperMeta,
    items: list[PrintPackItem],
    answer_mode: str,
) -> ExportResponse:
    from app.services.storage_service import get_storage_service

    job_id = str(uuid4())

    try:
        pdf_bytes = _generate_print_pack_pdf(
            title=title,
            paper_meta=paper_meta,
            items=items,
            answer_mode=answer_mode,
        )
        storage = get_storage_service()
        download_url = storage.upload_export(pdf_bytes, job_id, format="pdf")
        logger.info(
            "Print-pack export completed: job_id=%s answer_mode=%s items=%d url=%s",
            job_id,
            answer_mode,
            len(items),
            download_url,
        )
        return ExportResponse(job_id=job_id, status="completed", download_url=download_url)
    except Exception:
        logger.exception("Print-pack export failed: job_id=%s answer_mode=%s", job_id, answer_mode)
        return ExportResponse(job_id=job_id, status="failed", download_url=None)
