# -*- coding: utf-8 -*-
"""
Unicode-aware PDF Acknowledgment generator for Sewa Setu.
Supports Latin, Assamese, Bengali, and Devanagari scripts seamlessly.
"""

import os
from fpdf import FPDF

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS_DIR = os.path.join(BASE_DIR, "static", "fonts")


def generate_acknowledgment_pdf(cur, app_id):
    """
    Generate acknowledgment slip as PDF bytes with full Unicode support.
    """
    cur.execute(
        "SELECT application_no, applicant_name, mobile, dob, village, block, "
        "bank_account, ifsc, submitted_at, status FROM applications WHERE id = %s",
        (app_id,)
    )
    row = cur.fetchone()
    if not row:
        return b""

    pdf = FPDF()
    pdf.add_page()

    # Font setup
    noto_regular = os.path.join(FONTS_DIR, "NotoSans-Regular.ttf")
    noto_bold = os.path.join(FONTS_DIR, "NotoSans-Bold.ttf")
    noto_bengali = os.path.join(FONTS_DIR, "NotoSansBengali-Regular.ttf")
    noto_devanagari = os.path.join(FONTS_DIR, "NotoSansDevanagari-Regular.ttf")

    has_unicode_fonts = os.path.exists(noto_regular)

    if has_unicode_fonts:
        pdf.add_font("NotoSans", "", noto_regular)
        if os.path.exists(noto_bold):
            pdf.add_font("NotoSans", "B", noto_bold)
        else:
            pdf.add_font("NotoSans", "B", noto_regular)
        pdf.add_font("NotoSans", "I", noto_regular)

        fallbacks = []
        if os.path.exists(noto_bengali):
            pdf.add_font("NotoSansBengali", "", noto_bengali)
            fallbacks.append("NotoSansBengali")
        if os.path.exists(noto_devanagari):
            pdf.add_font("NotoSansDevanagari", "", noto_devanagari)
            fallbacks.append("NotoSansDevanagari")

        if fallbacks and hasattr(pdf, "set_fallback_fonts"):
            pdf.set_fallback_fonts(fallbacks)

        font_family = "NotoSans"
    else:
        font_family = "Helvetica"

    # Header
    pdf.set_font(font_family, "B", 14)
    pdf.cell(0, 10, "GOVERNMENT OF PURVANCHAL", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font(font_family, "", 11)
    pdf.cell(0, 8, "Department of Social Welfare", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.cell(0, 8, "Old Age Pension Scheme - Acknowledgment", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)

    # Clean vector border
    pdf.line(10, 12, 200, 12)
    pdf.line(10, 282, 200, 282)

    labels = [
        "Application No", "Applicant Name", "Mobile", "Date of Birth",
        "Village", "Block", "Bank Account", "IFSC", "Submitted At", "Status"
    ]

    pdf.set_font(font_family, "", 10)
    for label, val in zip(labels, row):
        val_str = "" if val is None else str(val)
        try:
            pdf.cell(60, 8, label, border=1)
            pdf.cell(0, 8, val_str, border=1, new_x="LMARGIN", new_y="NEXT")
        except Exception:
            # Fallback if an unsupported glyph is encountered
            pdf.cell(0, 8, val_str.encode("ascii", errors="replace").decode("ascii"), border=1, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)
    pdf.set_font(font_family, "I", 9)
    pdf.multi_cell(
        0, 5,
        "This is a computer generated acknowledgment. Processing SLA "
        "as per the Purvanchal Right to Public Services Act applies."
    )

    return bytes(pdf.output())
