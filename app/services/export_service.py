from io import BytesIO
from uuid import uuid4
import logging
from typing import Optional

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
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib import colors

from app.schemas.export import ExportQuestionItem, ExportResponse

logger = logging.getLogger("uvicorn.error")


def _base_doc_and_styles():
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=20,
        alignment=TA_CENTER,
        spaceAfter=30,
        spaceBefore=10,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1a1a1a"),
    )
    section_title_style = ParagraphStyle(
        "SectionTitle",
        parent=styles["Heading2"],
        fontSize=16,
        alignment=TA_LEFT,
        spaceAfter=15,
        spaceBefore=20,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#333333"),
        borderPadding=(5, 10, 5, 10),
        backColor=colors.HexColor("#f0f0f0"),
    )
    question_number_style = ParagraphStyle(
        "QuestionNumber",
        parent=styles["BodyText"],
        fontSize=14,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#0066cc"),
        spaceAfter=8,
    )
    question_content_style = ParagraphStyle(
        "QuestionContent",
        parent=styles["BodyText"],
        fontSize=12,
        alignment=TA_JUSTIFY,
        leading=20,
        leftIndent=20,
        spaceAfter=10,
    )
    answer_space_style = ParagraphStyle(
        "AnswerSpace",
        parent=styles["BodyText"],
        fontSize=10,
        textColor=colors.HexColor("#999999"),
        leftIndent=20,
        spaceAfter=15,
    )
    footer_style = ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontSize=9,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#999999"),
    )

    return buffer, doc, {
        "title": title_style,
        "section": section_title_style,
        "number": question_number_style,
        "content": question_content_style,
        "answer_space": answer_space_style,
        "footer": footer_style,
    }


def _add_answer_lines(story, doc, count=4):
    for _ in range(count):
        line = Table([["_" * 80]], colWidths=[doc.width])
        line.setStyle(
            TableStyle([
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#dddddd")),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
            ])
        )
        story.append(line)
        story.append(Spacer(1, 0.3 * cm))


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


def _generate_single_pdf(
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

    story.append(Paragraph("📝 原题", styles["section"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(_question_table(original_text, doc, styles["content"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("【答题区域】", styles["answer_space"]))
    _add_answer_lines(story, doc)
    story.append(Spacer(1, 1 * cm))

    if variants:
        story.append(PageBreak())
        story.append(Paragraph("🔄 变式题（举一反三）", styles["section"]))
        story.append(Spacer(1, 0.5 * cm))
        for i, variant in enumerate(variants, 1):
            question_elements = [Paragraph(f"<b>第 {i} 题</b>", styles["number"])]
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
        block.append(Paragraph(f"<b>第 {index} 题 · {title_line}</b>", styles["number"]))
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
            pdf_bytes = _generate_single_pdf(title, original_text or "", variants, include_images)

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
