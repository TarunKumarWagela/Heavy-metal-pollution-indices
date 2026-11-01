"""Report generation service — PDF, Excel, CSV."""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================ #
#  CSV Export                                                   #
# ============================================================ #

def generate_csv(samples: list[dict]) -> bytes:
    """Generate a CSV bytes object from a list of sample dicts."""
    if not samples:
        return b"No data\n"

    output = io.StringIO()
    fieldnames = list(samples[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(samples)
    return output.getvalue().encode("utf-8")


# ============================================================ #
#  Excel Export                                                 #
# ============================================================ #

def generate_excel(
    samples: list[dict],
    index_results: list[dict] | None = None,
    report_title: str = "HMPIAS Report",
) -> bytes:
    """Generate an Excel workbook with samples and optional index results."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ImportError:
        raise RuntimeError("openpyxl is required for Excel export. pip install openpyxl")

    wb = openpyxl.Workbook()

    # ---- Sheet 1: Sample Data ----
    ws1 = wb.active
    ws1.title = "Sample Data"

    # Title
    ws1["A1"] = report_title
    ws1["A1"].font = Font(bold=True, size=14, color="1F3D6E")
    ws1["A2"] = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    ws1["A2"].font = Font(italic=True, size=10, color="666666")

    header_fill = PatternFill("solid", fgColor="1F3D6E")
    header_font = Font(bold=True, color="FFFFFF")

    if samples:
        headers = list(samples[0].keys())
        for col_idx, header in enumerate(headers, 1):
            cell = ws1.cell(row=4, column=col_idx, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")

        for row_idx, sample in enumerate(samples, 5):
            for col_idx, header in enumerate(headers, 1):
                ws1.cell(row=row_idx, column=col_idx, value=sample.get(header))

        # Auto-width
        for col_idx in range(1, len(headers) + 1):
            ws1.column_dimensions[get_column_letter(col_idx)].width = 15

    # ---- Sheet 2: Index Results ----
    if index_results:
        ws2 = wb.create_sheet("Index Results")
        ws2["A1"] = "Pollution Index Results"
        ws2["A1"].font = Font(bold=True, size=14, color="1F3D6E")

        idx_headers = [
            "Sample ID", "Index Type", "Index Value",
            "Classification", "Standard Profile", "Metals Used",
        ]
        for col_idx, h in enumerate(idx_headers, 1):
            cell = ws2.cell(row=3, column=col_idx, value=h)
            cell.fill = header_fill
            cell.font = header_font

        for row_idx, r in enumerate(index_results, 4):
            ws2.cell(row=row_idx, column=1, value=r.get("sample_id"))
            ws2.cell(row=row_idx, column=2, value=r.get("index_type"))
            ws2.cell(row=row_idx, column=3, value=round(r.get("index_value", 0), 4))
            ws2.cell(row=row_idx, column=4, value=r.get("classification"))
            ws2.cell(row=row_idx, column=5, value=r.get("standard_profile"))
            ws2.cell(row=row_idx, column=6, value=", ".join(r.get("metals_included") or []))

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# ============================================================ #
#  PDF Report                                                   #
# ============================================================ #

def generate_pdf_report(
    sample_data: dict[str, Any],
    index_results: dict[str, Any],
    standard_profile: str = "BIS IS 10500",
) -> bytes:
    """
    Generate a professional PDF report using ReportLab.

    Returns PDF as bytes.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph,
            Spacer, HRFlowable,
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
    except ImportError:
        raise RuntimeError("reportlab is required. pip install reportlab")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    navy = colors.HexColor("#1F3D6E")
    teal = colors.HexColor("#0D9488")
    light_gray = colors.HexColor("#F1F5F9")

    title_style = ParagraphStyle(
        "Title", parent=styles["Title"],
        textColor=navy, fontSize=18, spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle", parent=styles["Normal"],
        textColor=teal, fontSize=11, spaceAfter=12,
    )
    heading_style = ParagraphStyle(
        "Heading2", parent=styles["Heading2"],
        textColor=navy, fontSize=13, spaceBefore=12, spaceAfter=6,
    )
    normal_style = styles["Normal"]
    small_style = ParagraphStyle(
        "Small", parent=styles["Normal"], fontSize=8, textColor=colors.gray
    )

    story = []

    # ---- Header ----
    story.append(Paragraph("HMPIAS", title_style))
    story.append(Paragraph("Heavy Metal Pollution Index Assessment System", subtitle_style))
    story.append(Paragraph("Groundwater Quality Assessment Report", heading_style))
    story.append(HRFlowable(width="100%", thickness=2, color=navy))
    story.append(Spacer(1, 0.3*cm))

    # ---- Report metadata ----
    meta = [
        ["Report Date:", datetime.now().strftime("%Y-%m-%d %H:%M")],
        ["Standard Profile:", standard_profile],
        ["Sample ID:", str(sample_data.get("sample_id", "N/A"))],
        ["State:", str(sample_data.get("state", "N/A"))],
        ["District:", str(sample_data.get("district", "N/A"))],
        ["Station:", str(sample_data.get("station", "N/A"))],
        ["Sample Date:", str(sample_data.get("sample_date", "N/A"))],
    ]
    if sample_data.get("latitude"):
        meta.append(["Coordinates:", f"{sample_data['latitude']:.4f}°N, {sample_data['longitude']:.4f}°E"])

    meta_table = Table(meta, colWidths=[4*cm, 12*cm])
    meta_table.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("TEXTCOLOR", (0,0), (0,-1), navy),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [light_gray, colors.white]),
        ("GRID", (0,0), (-1,-1), 0.5, colors.lightgrey),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 0.5*cm))

    # ---- Index Results ----
    story.append(Paragraph("Pollution Index Results", heading_style))

    indices = index_results.get("indices", {})
    idx_data = [["Index", "Value", "Classification", "Standard"]]

    for idx_name, idx_val in indices.items():
        if "error" in idx_val:
            idx_data.append([idx_name, "Error", idx_val["error"][:50], standard_profile])
        else:
            val_key = {"HPI": "hpi", "HEI": "hei", "Cd_index": "cd_index"}.get(idx_name, "value")
            val = idx_val.get(val_key, "N/A")
            val_str = f"{val:.4f}" if isinstance(val, float) else str(val)
            idx_data.append([
                idx_name, val_str,
                idx_val.get("classification", "N/A"),
                standard_profile,
            ])

    if len(idx_data) > 1:
        idx_table = Table(idx_data, colWidths=[3*cm, 3*cm, 7*cm, 3*cm])
        idx_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), navy),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [light_gray, colors.white]),
            ("GRID", (0,0), (-1,-1), 0.5, colors.lightgrey),
            ("ALIGN", (1,0), (1,-1), "CENTER"),
        ]))
        story.append(idx_table)

    # ---- HPI Contributions ----
    hpi_data = indices.get("HPI", {})
    if "per_metal" in hpi_data and hpi_data["per_metal"]:
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph("HPI Metal Contribution Breakdown", heading_style))

        contrib_data = [["Metal", "Measured (mg/L)", "Limit (mg/L)", "Qi (Sub-index)", "EC", "% Contribution"]]
        for pm in hpi_data["per_metal"]:
            contrib_data.append([
                pm["metal"],
                f"{pm['measured_concentration_mg_L']:.4f}",
                f"{pm['reference_limit_mg_L']:.4f}",
                f"{pm['sub_index_Qi']:.2f}",
                f"{pm['effective_contribution']:.4f}",
                f"{pm['percentage_contribution']:.2f}%",
            ])

        contrib_table = Table(contrib_data, colWidths=[2*cm, 3*cm, 3*cm, 2.5*cm, 2.5*cm, 3*cm])
        contrib_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), teal),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [light_gray, colors.white]),
            ("GRID", (0,0), (-1,-1), 0.5, colors.lightgrey),
            ("ALIGN", (1,0), (-1,-1), "CENTER"),
        ]))
        story.append(contrib_table)

    # ---- Methodology ----
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("Scientific Methodology & Citations", heading_style))
    story.append(HRFlowable(width="100%", thickness=1, color=teal))
    story.append(Spacer(1, 0.2*cm))

    citations = [
        ("HPI", "Mohan, S.V., Nithila, P., & Reddy, S.J. (1996). J. Environ. Sci. Health Part A, 31(2), 283–289. https://doi.org/10.1080/10934529609376357"),
        ("HEI", "Edet, A.E., & Offiong, O.E. (2002). GeoJournal, 57(4), 295–304. https://doi.org/10.1023/B:GEJO.0000007250.92458.de"),
        ("Cd_index", "Backman, B., et al. (1998). Environmental Geology, 36(1–2), 55–64. https://doi.org/10.1007/s002540050320"),
        ("BIS Standard", "Bureau of Indian Standards. IS 10500:2012 (Amendment 2019). https://bis.gov.in"),
        ("WHO Standard", "WHO (2022). Guidelines for Drinking-water Quality, 4th ed. + addenda. https://www.who.int"),
    ]
    for name, citation in citations:
        story.append(Paragraph(f"<b>{name}:</b> {citation}", small_style))
        story.append(Spacer(1, 0.15*cm))

    # ---- Disclaimer ----
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("⚠ Disclaimer", heading_style))
    story.append(Paragraph(
        "This report is generated for scientific research and monitoring purposes only. "
        "Index classifications are literature-based and not equivalent to regulatory determinations. "
        "Consult qualified environmental professionals before taking regulatory action. "
        "BDL measurements were excluded from calculations, not set to zero.",
        normal_style,
    ))

    doc.build(story)
    return buffer.getvalue()
