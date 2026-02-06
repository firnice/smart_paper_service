from io import BytesIO
from uuid import uuid4
import logging
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib import colors

from app.schemas.export import ExportResponse

logger = logging.getLogger("uvicorn.error")


def _generate_pdf(
    title: str,
    original_text: str,
    variants: list[str],
    include_images: bool = False
) -> bytes:
    """
    生成 PDF 字节流（改进版排版）

    Args:
        title: 文档标题
        original_text: 原题文本
        variants: 变式题列表
        include_images: 是否包含图片（暂未实现）

    Returns:
        PDF 字节流
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=2.5*cm,
        bottomMargin=2.5*cm,
        leftMargin=2.5*cm,
        rightMargin=2.5*cm,
    )

    # 样式设置
    styles = getSampleStyleSheet()

    # 自定义标题样式
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        alignment=TA_CENTER,
        spaceAfter=30,
        spaceBefore=10,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1a1a1a'),
    )

    # 自定义大标题样式（原题/变式题）
    section_title_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontSize=16,
        alignment=TA_LEFT,
        spaceAfter=15,
        spaceBefore=20,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#333333'),
        borderPadding=(5, 10, 5, 10),
        backColor=colors.HexColor('#f0f0f0'),
    )

    # 题目编号样式
    question_number_style = ParagraphStyle(
        'QuestionNumber',
        parent=styles['BodyText'],
        fontSize=14,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#0066cc'),
        spaceAfter=8,
    )

    # 题目内容样式
    question_content_style = ParagraphStyle(
        'QuestionContent',
        parent=styles['BodyText'],
        fontSize=12,
        alignment=TA_JUSTIFY,
        leading=20,  # 行间距
        leftIndent=20,  # 左缩进
        spaceAfter=10,
    )

    # 答题空间提示样式
    answer_space_style = ParagraphStyle(
        'AnswerSpace',
        parent=styles['BodyText'],
        fontSize=10,
        textColor=colors.HexColor('#999999'),
        leftIndent=20,
        spaceAfter=15,
    )

    # 构建文档内容
    story = []

    # ===== 文档标题 =====
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 0.5*cm))

    # 添加装饰线
    line_table = Table([['']], colWidths=[doc.width])
    line_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 2, colors.HexColor('#0066cc')),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 1*cm))

    # ===== 原题部分 =====
    story.append(Paragraph("📝 原题", section_title_style))
    story.append(Spacer(1, 0.5*cm))

    # 原题框格
    original_formatted = original_text.replace("\n", "<br/>")
    question_box = [
        [Paragraph(original_formatted, question_content_style)]
    ]
    question_table = Table(question_box, colWidths=[doc.width])
    question_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fafafa')),
        ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor('#cccccc')),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ('LEFTPADDING', (0, 0), (-1, -1), 15),
        ('RIGHTPADDING', (0, 0), (-1, -1), 15),
    ]))
    story.append(question_table)
    story.append(Spacer(1, 0.3*cm))

    # 答题空间提示
    story.append(Paragraph("【答题区域】", answer_space_style))

    # 答题空间（横线）
    for _ in range(4):
        line = Table([['_' * 80]], colWidths=[doc.width])
        line.setStyle(TableStyle([
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#dddddd')),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
        ]))
        story.append(line)
        story.append(Spacer(1, 0.3*cm))

    story.append(Spacer(1, 1*cm))

    # ===== 变式题部分 =====
    if variants:
        # 变式题可以分页
        story.append(PageBreak())

        story.append(Paragraph("🔄 变式题（举一反三）", section_title_style))
        story.append(Spacer(1, 0.5*cm))

        for i, variant in enumerate(variants, 1):
            # 每道变式题用 KeepTogether 保持在同一页
            question_elements = []

            # 题号
            question_elements.append(
                Paragraph(f"<b>第 {i} 题</b>", question_number_style)
            )

            # 题目内容框格
            variant_formatted = variant.replace("\n", "<br/>")
            variant_box = [
                [Paragraph(variant_formatted, question_content_style)]
            ]
            variant_table = Table(variant_box, colWidths=[doc.width])
            variant_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9ff')),
                ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor('#b3c6ff')),
                ('TOPPADDING', (0, 0), (-1, -1), 15),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
                ('LEFTPADDING', (0, 0), (-1, -1), 15),
                ('RIGHTPADDING', (0, 0), (-1, -1), 15),
            ]))
            question_elements.append(variant_table)
            question_elements.append(Spacer(1, 0.3*cm))

            # 答题空间
            question_elements.append(
                Paragraph("【答题区域】", answer_space_style)
            )
            for _ in range(4):
                line = Table([['_' * 80]], colWidths=[doc.width])
                line.setStyle(TableStyle([
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#dddddd')),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                ]))
                question_elements.append(line)
                question_elements.append(Spacer(1, 0.3*cm))

            # 题目间距
            question_elements.append(Spacer(1, 1*cm))

            # 添加分隔线
            if i < len(variants):
                divider = Table([['']], colWidths=[doc.width])
                divider.setStyle(TableStyle([
                    ('LINEBELOW', (0, 0), (-1, -1), 1, colors.HexColor('#e0e0e0')),
                ]))
                question_elements.append(divider)
                question_elements.append(Spacer(1, 1*cm))

            # 使用 KeepTogether 保持每道题完整
            story.append(KeepTogether(question_elements))

    # 页脚说明
    story.append(Spacer(1, 1*cm))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#999999'),
    )
    story.append(Paragraph("—— 智能错题本练习卷 ——", footer_style))

    # 生成 PDF
    doc.build(story)
    buffer.seek(0)

    logger.info(
        "PDF generated: title=%s, variants=%d, size=%d bytes",
        title,
        len(variants),
        buffer.getbuffer().nbytes
    )

    return buffer.read()


def create_export(
    title: str,
    original_text: str,
    variants: list[str],
    include_images: bool,
) -> ExportResponse:
    """
    创建导出任务（同步生成 PDF）

    Args:
        title: 文档标题
        original_text: 原题文本
        variants: 变式题列表
        include_images: 是否包含图片

    Returns:
        导出响应（包含下载 URL）
    """
    from app.services.storage_service import get_storage_service

    job_id = str(uuid4())

    try:
        # 生成 PDF
        pdf_bytes = _generate_pdf(title, original_text, variants, include_images)

        # 上传到存储
        storage = get_storage_service()
        download_url = storage.upload_export(pdf_bytes, job_id, format="pdf")

        logger.info("Export completed: job_id=%s url=%s", job_id, download_url)

        return ExportResponse(
            job_id=job_id,
            status="completed",
            download_url=download_url,
        )

    except Exception as e:
        logger.exception("Export failed: job_id=%s", job_id)
        return ExportResponse(
            job_id=job_id,
            status="failed",
            download_url=None,
        )
