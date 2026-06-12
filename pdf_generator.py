# EduCore - PDF Generator

import json
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def generate_test_pdf(test):
    """Test savollarini PDF formatga o'girish.

    Args:
        test: Test model object (topic, level, questions JSON string)

    Returns:
        BytesIO: PDF fayl buffer
    """
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=12
    )

    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        alignment=TA_CENTER,
        spaceAfter=20
    )

    question_style = ParagraphStyle(
        'QuestionStyle',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=6,
        spaceBefore=12,
        leftIndent=0
    )

    option_style = ParagraphStyle(
        'OptionStyle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=3,
        leftIndent=20
    )

    elements = []

    # Title
    elements.append(Paragraph(f"Test: {test.topic}", title_style))
    elements.append(Paragraph(f"Daraja: {test.level}", subtitle_style))
    elements.append(Spacer(1, 0.5 * cm))

    # Parse questions
    questions = json.loads(test.questions)

    for i, q in enumerate(questions, 1):
        # Question text
        question_text = f"<b>{i}.</b> {q['question']}"
        elements.append(Paragraph(question_text, question_style))

        # Options
        for key, value in q['options'].items():
            option_text = f"{key}) {value}"
            elements.append(Paragraph(option_text, option_style))

        elements.append(Spacer(1, 0.3 * cm))

    # Footer
    elements.append(Spacer(1, 1 * cm))
    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_CENTER
    )
    elements.append(Paragraph("EduCore Uzbekistan", footer_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer
