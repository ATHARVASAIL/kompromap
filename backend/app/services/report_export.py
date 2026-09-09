"""DOCX and PDF export for engagement reports.

Uses python-docx for .docx and reportlab for .pdf. Both libraries are
added to requirements.txt — they are pure-Python wheels with no system
dependencies, so they don't bloat the image.
"""
from __future__ import annotations

import io
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import HRFlowable

SEVERITY_HEX = {
    "Critical": "#F2454E",
    "High": "#F5883A",
    "Medium": "#F0C93A",
    "Low": "#4C8DF0",
    "Informational": "#6B7488",
}

SEVERITY_ORDER = ["Critical", "High", "Medium", "Low", "Informational"]


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _render_pdf(report: dict) -> bytes:
    """Render an EngagementReport dict to a self-contained PDF."""
    buf = io.BytesIO()

    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=25 * mm,
        bottomMargin=20 * mm,
        title=f"Kompromap — {report.get('engagement_name', 'Engagement')}",
        author="Kompromap",
    )

    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")

    def _header(canvas, doc_obj):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#6B7488"))
        canvas.drawString(doc_obj.leftMargin, doc_obj.height + doc_obj.topMargin - 8 * mm,
                          f"Kompromap — {report.get('engagement_name', 'Engagement')}")
        canvas.drawRightString(doc_obj.width + doc_obj.leftMargin, doc_obj.height + doc_obj.topMargin - 8 * mm,
                               f"Generated {datetime.now():%Y-%m-%d}")
        canvas.setStrokeColor(colors.HexColor("#232A38"))
        canvas.setLineWidth(0.5)
        canvas.line(doc_obj.leftMargin, doc_obj.height + doc_obj.topMargin - 10 * mm,
                    doc_obj.width + doc_obj.leftMargin, doc_obj.height + doc_obj.topMargin - 10 * mm)
        canvas.restoreState()

    def _footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#6B7488"))
        canvas.drawCentredString(doc_obj.width / 2 + doc_obj.leftMargin, 12 * mm, f"Page {doc_obj.page}")
        canvas.setStrokeColor(colors.HexColor("#232A38"))
        canvas.setLineWidth(0.5)
        canvas.line(doc_obj.leftMargin, 14 * mm, doc_obj.width + doc_obj.leftMargin, 14 * mm)
        canvas.restoreState()

    doc.addPageTemplates([
        PageTemplate(id="main", frames=frame, onPage=_header, onPageEnd=_footer),
    ])

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("KpTitle", parent=styles["Title"], fontSize=18, spaceAfter=6,
                                  textColor=colors.HexColor("#E7EAF0"), fontName="Helvetica-Bold")
    h1 = ParagraphStyle("KpH1", parent=styles["Heading1"], fontSize=14, spaceBefore=16, spaceAfter=6,
                         textColor=colors.HexColor("#E7EAF0"), fontName="Helvetica-Bold")
    h2 = ParagraphStyle("KpH2", parent=styles["Heading2"], fontSize=11, spaceBefore=10, spaceAfter=4,
                         textColor=colors.HexColor("#CBD5E1"), fontName="Helvetica-Bold")
    body = ParagraphStyle("KpBody", parent=styles["BodyText"], fontSize=9, leading=13,
                           textColor=colors.HexColor("#CBD5E1"), spaceAfter=4)
    mono = ParagraphStyle("KpMono", parent=styles["Code"], fontSize=8, leading=11,
                           textColor=colors.HexColor("#9CA3AF"), spaceAfter=3)
    small = ParagraphStyle("KpSmall", parent=styles["BodyText"], fontSize=7, leading=10,
                            textColor=colors.HexColor("#6B7488"))

    story: list[Any] = []

    # Title
    story.append(Paragraph(report.get("engagement_name", "Engagement Report"), title_style))
    story.append(Paragraph(f"Generated {datetime.now():%Y-%m-%d %H:%M}", small))
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#232A38")))
    story.append(Spacer(1, 6 * mm))

    # Summary block
    s = report.get("summary", {})
    story.append(Paragraph("Summary", h1))
    summary_data = [
        ["Finding count", str(s.get("finding_count", 0))],
        ["Confirmed", str(s.get("confirmed", 0))],
        ["Unverified", str(s.get("unverified", 0))],
        ["False positives", str(s.get("false_positives", 0))],
        ["Avg CVSS", f"{s.get('avg_cvss', 0):.1f}"],
        ["Attack paths", str(s.get("attack_path_count", 0))],
    ]
    t = Table(summary_data, colWidths=[80, 80])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#0F131B")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#CBD5E1")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#232A38")),
    ]))
    story.append(t)
    story.append(Spacer(1, 8 * mm))

    # Findings by severity
    story.append(Paragraph("Findings by Severity", h1))
    sev_counts = s.get("findings_by_severity", {})
    if sev_counts:
        sev_data = [["Severity", "Count"]]
        for sev in SEVERITY_ORDER:
            if sev_counts.get(sev, 0) > 0:
                sev_data.append([sev, str(sev_counts[sev])])
        st = Table(sev_data, colWidths=[80, 60])
        st.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F131B")),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#CBD5E1")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#232A38")),
        ]))
        story.append(st)
        story.append(Spacer(1, 6 * mm))

    # Attack chains
    chains = report.get("attack_chains", [])
    if chains:
        story.append(Paragraph("Top Attack Chains", h1))
        for i, chain in enumerate(chains[:5], 1):
            story.append(Paragraph(f"Chain {i} — ease score {chain.get('ease_score', 0):.2f}", h2))
            steps = chain.get("steps", [])
            for step in steps:
                story.append(Paragraph(
                    f"<b>{step.get('node_type', '?')}:</b> {step.get('title', '?')}", body))
                cost = step.get("cost", 0)
                story.append(Paragraph(f"  Cost: {cost:.3f}", mono))
            story.append(Spacer(1, 3 * mm))

    # Detailed findings
    findings = report.get("findings", [])
    if findings:
        story.append(PageBreak())
        story.append(Paragraph("Detailed Findings", h1))
        for f in findings:
            sev = f.get("severity", "Informational")
            color = SEVERITY_HEX.get(sev, "#6B7488")
            story.append(Paragraph(f"<font color='#{_hex_to_rgb(color)[0]:02x}{_hex_to_rgb(color)[1]:02x}{_hex_to_rgb(color)[2]:02x}'><b>[{sev}]</b></font> {f.get('title', '?')}", h2))
            if f.get("cwe"):
                story.append(Paragraph(f"CWE: {f['cwe']}", mono))
            if f.get("cvss_score") is not None:
                story.append(Paragraph(f"CVSS: {f['cvss_score']:.1f}", mono))
            if f.get("description"):
                story.append(Paragraph(f["description"], body))
            if f.get("remediation"):
                story.append(Paragraph(f"<b>Remediation:</b> {f['remediation']}", body))
            story.append(HRFlowable(width="100%", thickness=0.3, color=colors.HexColor("#232A38")))
            story.append(Spacer(1, 2 * mm))

    doc.build(story)
    return buf.getvalue()


def _render_docx(report: dict) -> bytes:
    """Render an EngagementReport dict to a .docx file."""
    try:
        from docx import Document  # type: ignore
        from docx.shared import Inches, Pt, RGBColor  # type: ignore
        from docx.enum.text import WD_ALIGN_PARAGRAPH  # type: ignore
    except ImportError as exc:
        raise RuntimeError("python-docx is not installed. Add it to requirements.txt.") from exc

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10)
    style.font.color.rgb = RGBColor(0xCB, 0xD5, 0xE1)

    # Title
    title = doc.add_heading(report.get("engagement_name", "Engagement Report"), level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for run in title.runs:
        run.font.color.rgb = RGBColor(0xE7, 0xEA, 0xF0)

    doc.add_paragraph(f"Generated {datetime.now():%Y-%m-%d %H:%M}").runs[0].font.color.rgb = RGBColor(0x6B, 0x74, 0x88)

    # Summary
    doc.add_heading("Summary", level=1)
    s = report.get("summary", {})
    table = doc.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    for key, val in [
        ("Finding count", str(s.get("finding_count", 0))),
        ("Confirmed", str(s.get("confirmed", 0))),
        ("Unverified", str(s.get("unverified", 0))),
        ("False positives", str(s.get("false_positives", 0))),
        ("Avg CVSS", f"{s.get('avg_cvss', 0):.1f}"),
        ("Attack paths", str(s.get("attack_path_count", 0))),
    ]:
        row = table.add_row().cells
        row[0].text = key
        row[1].text = val
        for cell in row:
            for p in cell.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9)

    # Findings by severity
    sev_counts = s.get("findings_by_severity", {})
    if sev_counts:
        doc.add_heading("Findings by Severity", level=1)
        sev_table = doc.add_table(rows=1, cols=2)
        sev_table.style = "Table Grid"
        hdr = sev_table.rows[0].cells
        hdr[0].text = "Severity"
        hdr[1].text = "Count"
        for sev in SEVERITY_ORDER:
            if sev_counts.get(sev, 0) > 0:
                row = sev_table.add_row().cells
                row[0].text = sev
                row[1].text = str(sev_counts[sev])

    # Detailed findings
    findings = report.get("findings", [])
    if findings:
        doc.add_page_break()
        doc.add_heading("Detailed Findings", level=1)
        for f in findings:
            sev = f.get("severity", "Informational")
            h = doc.add_heading(f"[{sev}] {f.get('title', '?')}", level=2)
            color = SEVERITY_HEX.get(sev, "#6B7488")
            rgb = _hex_to_rgb(color)
            for run in h.runs:
                run.font.color.rgb = RGBColor(*rgb)
            if f.get("cwe"):
                doc.add_paragraph(f"CWE: {f['cwe']}").runs[0].font.size = Pt(9)
            if f.get("cvss_score") is not None:
                doc.add_paragraph(f"CVSS: {f['cvss_score']:.1f}").runs[0].font.size = Pt(9)
            if f.get("description"):
                doc.add_paragraph(f["description"])
            if f.get("remediation"):
                p = doc.add_paragraph()
                r = p.add_run("Remediation: ")
                r.bold = True
                p.add_run(f["remediation"])

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def render_report_docx(report: dict) -> bytes:
    """Public entry point — DOCX bytes."""
    return _render_docx(report)


def render_report_pdf(report: dict) -> bytes:
    """Public entry point — PDF bytes."""
    return _render_pdf(report)
