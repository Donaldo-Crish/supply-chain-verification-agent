from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from io import BytesIO
from datetime import datetime


# ─── COLOUR PALETTE ───────────────────────────────────────────────────────────
DARK_BG     = colors.HexColor("#0f1117")
ACCENT_BLUE = colors.HexColor("#1c6ef3")
FLAG_RED    = colors.HexColor("#c0392b")
VERIFY_GRN  = colors.HexColor("#1a7a4a")
LIGHT_GREY  = colors.HexColor("#f0f2f6")
MID_GREY    = colors.HexColor("#6b7280")
TEXT_DARK   = colors.HexColor("#111827")
WHITE       = colors.white


def _styles():
    base = getSampleStyleSheet()

    custom = {
        "cover_title": ParagraphStyle(
            "cover_title",
            fontName="Helvetica-Bold",
            fontSize=22,
            textColor=WHITE,
            leading=28,
            alignment=TA_LEFT,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            fontName="Helvetica",
            fontSize=10,
            textColor=colors.HexColor("#a0aec0"),
            leading=14,
            alignment=TA_LEFT,
        ),
        "section_head": ParagraphStyle(
            "section_head",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=ACCENT_BLUE,
            spaceBefore=14,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            fontName="Helvetica",
            fontSize=9,
            textColor=TEXT_DARK,
            leading=14,
            spaceAfter=4,
        ),
        "label": ParagraphStyle(
            "label",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=MID_GREY,
        ),
        "status_verified": ParagraphStyle(
            "status_verified",
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=VERIFY_GRN,
        ),
        "status_flagged": ParagraphStyle(
            "status_flagged",
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=FLAG_RED,
        ),
        "footer": ParagraphStyle(
            "footer",
            fontName="Helvetica",
            fontSize=7,
            textColor=MID_GREY,
            alignment=TA_CENTER,
        ),
        "ai_body": ParagraphStyle(
            "ai_body",
            fontName="Helvetica",
            fontSize=9,
            textColor=TEXT_DARK,
            leading=15,
            leftIndent=8,
            rightIndent=8,
        ),
    }
    return custom


def generate_audit_pdf(product_data: dict, journey: list, ai_report: str) -> bytes:
    """
    Generate a polished audit report PDF.
    Returns raw bytes — pass directly to st.download_button.
    """
    buffer = BytesIO()
    PAGE_W, PAGE_H = A4
    MARGIN = 20 * mm

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title=f"Audit Report — {product_data.get('product_id', 'N/A')}",
        author="Supply Chain Verification Agent",
    )

    S = _styles()
    story = []
    now = datetime.now().strftime("%d %B %Y, %H:%M:%S")
    pid = product_data.get("product_id", "N/A")
    status = product_data.get("status", "UNKNOWN")

    # ── HEADER BANNER ────────────────────────────────────────────────────────
    header_data = [[
        Paragraph("SUPPLY CHAIN VERIFICATION AGENT", S["cover_title"]),
        Paragraph(f"Report generated<br/>{now}", S["cover_sub"]),
    ]]
    header_table = Table(header_data, colWidths=[110 * mm, 60 * mm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), DARK_BG),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",(0, 0), (-1, -1), 10),
        ("RIGHTPADDING",(0,0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING",(0,0),(-1, -1), 12),
        ("ALIGN",      (1, 0), (1,  0),  "RIGHT"),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8 * mm))

    # ── PRODUCT ID + STATUS ROW ───────────────────────────────────────────────
    status_style = S["status_verified"] if status == "VERIFIED" else S["status_flagged"]
    status_label = "✔  VERIFIED" if status == "VERIFIED" else "✘  FLAGGED FOR INVESTIGATION"
    status_color = VERIFY_GRN if status == "VERIFIED" else FLAG_RED

    id_status_data = [[
        Paragraph(f"<b>Product ID:</b>  {pid}", S["body"]),
        Paragraph(status_label, status_style),
    ]]
    id_status_table = Table(id_status_data, colWidths=[85 * mm, 85 * mm])
    id_status_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), LIGHT_GREY),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ALIGN",         (1, 0), (1,  0),  "RIGHT"),
        ("RIGHTPADDING",  (1, 0), (1,  0),  10),
        ("LINEBELOW",     (0, 0), (-1, -1), 2, status_color),
    ]))
    story.append(id_status_table)
    story.append(Spacer(1, 5 * mm))

    # ── PRODUCT DETAILS ───────────────────────────────────────────────────────
    story.append(Paragraph("PRODUCT DETAILS", S["section_head"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=ACCENT_BLUE))
    story.append(Spacer(1, 3 * mm))

    fields = [
        ("Product Name",    product_data.get("name", "N/A")),
        ("Manufacturer",    product_data.get("manufacturer", "N/A")),
        ("Batch ID",        product_data.get("batch_id", "N/A")),
        ("Manufacture Date",product_data.get("manufacture_date", "N/A")),
        ("Current Location",product_data.get("current_location", "N/A")),
        ("Ledger Status",   status),
    ]

    detail_rows = [[
        Paragraph(label, S["label"]),
        Paragraph(str(value), S["body"])
    ] for label, value in fields]

    detail_table = Table(detail_rows, colWidths=[50 * mm, 120 * mm])
    detail_table.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS",(0, 0), (-1, -1), [WHITE, LIGHT_GREY]),
        ("LINEBELOW",     (0, -1),(-1, -1), 0.5, MID_GREY),
    ]))
    story.append(detail_table)
    story.append(Spacer(1, 6 * mm))

    # ── CHAIN OF CUSTODY ──────────────────────────────────────────────────────
    story.append(Paragraph("CHAIN OF CUSTODY", S["section_head"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=ACCENT_BLUE))
    story.append(Spacer(1, 3 * mm))

    coc_header = [
        Paragraph("Stage",    S["label"]),
        Paragraph("Location", S["label"]),
        Paragraph("Date",     S["label"]),
        Paragraph("Status",   S["label"]),
    ]
    coc_rows = [coc_header]

    for step in journey:
        v = step.get("verified", False)
        vstyle = ParagraphStyle("vs", fontName="Helvetica-Bold", fontSize=9,
                                textColor=VERIFY_GRN if v else FLAG_RED)
        coc_rows.append([
            Paragraph(step.get("stage", ""),    S["body"]),
            Paragraph(step.get("location", ""), S["body"]),
            Paragraph(step.get("date", ""),     S["body"]),
            Paragraph("VERIFIED" if v else "UNVERIFIED", vstyle),
        ])

    coc_table = Table(coc_rows, colWidths=[40 * mm, 50 * mm, 40 * mm, 40 * mm])
    coc_style = [
        ("BACKGROUND",    (0, 0), (-1,  0), DARK_BG),
        ("TEXTCOLOR",     (0, 0), (-1,  0), WHITE),
        ("FONTNAME",      (0, 0), (-1,  0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1,  0), 9),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, LIGHT_GREY]),
        ("GRID",          (0, 0), (-1, -1), 0.3, MID_GREY),
    ]
    # Red left border on unverified rows
    for i, step in enumerate(journey, start=1):
        if not step.get("verified", True):
            coc_style.append(("LINEBEFORE", (0, i), (0, i), 3, FLAG_RED))

    coc_table.setStyle(TableStyle(coc_style))
    story.append(coc_table)
    story.append(Spacer(1, 6 * mm))

    # ── AI FORENSIC REPORT ────────────────────────────────────────────────────
    story.append(Paragraph("AI FORENSIC AUDIT REPORT", S["section_head"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=ACCENT_BLUE))
    story.append(Spacer(1, 3 * mm))

    # Wrap AI report in a shaded box
    ai_box_data = [[Paragraph(ai_report.replace("\n", "<br/>"), S["ai_body"])]]
    ai_box = Table(ai_box_data, colWidths=[170 * mm])
    ai_box.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#eef2ff")),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LINEBEFORE",    (0, 0), (0,  -1), 3, ACCENT_BLUE),
    ]))
    story.append(ai_box)
    story.append(Spacer(1, 8 * mm))

    # ── FOOTER ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.3, color=MID_GREY))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        f"This report was auto-generated by the Supply Chain Verification Agent powered by LLaMA 3.3 70B via Groq API. "
        f"Generated: {now}. For internal audit use only.",
        S["footer"]
    ))

    doc.build(story)
    return buffer.getvalue()