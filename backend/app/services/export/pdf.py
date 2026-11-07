"""Markdown → PDF rendering with ReportLab.

A deliberately small Markdown subset is supported (headings, paragraphs,
lists, block quotes, pipe tables, fenced code, bold/italic/code/links), which
covers everything LessonForge itself produces.
"""
from __future__ import annotations

import io
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ...utils.errors import AppError

NAVY = colors.HexColor("#1B2638")
TEAL = colors.HexColor("#0F766E")
MUTED = colors.HexColor("#5B6475")
RULE = colors.HexColor("#E4E1DA")
PAPER = colors.HexColor("#F7F5F0")


def _styles():
    ss = getSampleStyleSheet()
    base = ParagraphStyle("body", parent=ss["BodyText"], fontName="Helvetica", fontSize=10, leading=14.5,
                          textColor=NAVY, alignment=TA_LEFT, spaceAfter=5)
    return {
        "body": base,
        "h1": ParagraphStyle("h1", parent=base, fontName="Helvetica-Bold", fontSize=20, leading=25, spaceAfter=10),
        "h2": ParagraphStyle("h2", parent=base, fontName="Helvetica-Bold", fontSize=14, leading=19,
                             spaceBefore=12, spaceAfter=6, textColor=TEAL),
        "h3": ParagraphStyle("h3", parent=base, fontName="Helvetica-Bold", fontSize=11.5, leading=16, spaceBefore=8),
        "quote": ParagraphStyle("quote", parent=base, leftIndent=8, textColor=MUTED, backColor=PAPER,
                                borderPadding=(4, 6, 4, 6), spaceAfter=2),
        "code": ParagraphStyle("code", parent=base, fontName="Courier", fontSize=8.5, leading=11,
                               backColor=PAPER, borderPadding=6, leftIndent=4),
        "cell": ParagraphStyle("cell", parent=base, fontSize=8.5, leading=11, spaceAfter=0),
        "cellh": ParagraphStyle("cellh", parent=base, fontSize=8.5, leading=11, spaceAfter=0,
                                fontName="Helvetica-Bold"),
    }


def inline(text: str) -> str:
    """Convert inline markdown to ReportLab mini-HTML (escaping everything else)."""
    codes: list[str] = []

    def stash(m):
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", stash, text)
    text = escape(text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<link href="\2" color="#0F766E">\1</link>', text)
    text = re.sub(r"&lt;(https?://[^&\s]+)&gt;", r'<link href="\1" color="#0F766E">\1</link>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<i>\1</i>", text)
    text = re.sub(r"(?<![\w])_(?!\s)(.+?)(?<!\s)_(?![\w])", r"<i>\1</i>", text)
    text = re.sub(r"\[(C\d+)\]", r'<font color="#0F766E" size="7"><super>\1</super></font>', text)
    for i, code in enumerate(codes):
        text = text.replace(f"\x00{i}\x00", f'<font name="Courier" backColor="#F2EFE8">{escape(code)}</font>')
    return text


def _table(rows: list[list[str]], st) -> Table:
    data = [[Paragraph(inline(c), st["cellh"] if r == 0 else st["cell"]) for c in row] for r, row in enumerate(rows)]
    ncols = max(len(r) for r in rows)
    data = [row + [""] * (ncols - len(row)) for row in data]
    width = 170 * mm
    # Size columns by their longest cell (clamped) so short columns like "#" stay narrow.
    lengths = [max(min(len(r[c]) if c < len(r) else 0, 60), 9) for c in range(ncols) for r in rows]
    weights = [max(lengths[c * len(rows):(c + 1) * len(rows)]) for c in range(ncols)]
    t = Table(data, colWidths=[width * w / sum(weights) for w in weights], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PAPER),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def markdown_to_flowables(md: str) -> list:
    st = _styles()
    flow: list = []
    lines = md.splitlines()
    i = 0
    para: list[str] = []

    def flush_para():
        if para:
            flow.append(Paragraph(inline(" ".join(para)), st["body"]))
            para.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_para()
            i += 1
            block = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            flow.append(Preformatted("\n".join(block), st["code"]))
            flow.append(Spacer(1, 4))
            i += 1
            continue
        if not stripped:
            flush_para()
            i += 1
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            flush_para()
            level = min(len(m.group(1)), 3)
            flow.append(Paragraph(inline(m.group(2)), st[f"h{level}"]))
            i += 1
            continue
        if stripped.startswith("|"):
            flush_para()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            if rows:
                flow.append(_table(rows, st))
                flow.append(Spacer(1, 6))
            continue
        if stripped.startswith(">"):
            flush_para()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            flow.append(Paragraph("<br/>".join(inline(q) for q in quote), st["quote"]))
            flow.append(Spacer(1, 4))
            continue
        lm = re.match(r"^(\s*)([-*]|\d+\.|[A-Z]\.)\s+(.*)$", line)
        if lm:
            flush_para()
            items, ordered = [], lm.group(2)[0].isdigit()
            while i < len(lines):
                lm2 = re.match(r"^(\s*)([-*]|\d+\.|[A-Z]\.)\s+(.*)$", lines[i])
                if not lm2:
                    break
                items.append(ListItem(Paragraph(inline(lm2.group(3)), st["body"]), leftIndent=14))
                i += 1
            flow.append(ListFlowable(items, bulletType="1" if ordered else "bullet", start="1" if ordered else None,
                                     leftIndent=14, bulletFontSize=8))
            continue
        para.append(stripped)
        i += 1
    flush_para()
    return flow


def render_pdf(markdown_text: str, title: str, footer: str) -> bytes:
    try:
        buf = io.BytesIO()

        def on_page(canvas, doc):
            canvas.saveState()
            canvas.setFont("Helvetica", 7.5)
            canvas.setFillColor(MUTED)
            canvas.drawString(20 * mm, 10 * mm, footer[:150])
            canvas.drawRightString(190 * mm, 10 * mm, f"LessonForge · page {doc.page}")
            canvas.restoreState()

        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                                topMargin=18 * mm, bottomMargin=18 * mm, title=title, author="LessonForge")
        doc.build(markdown_to_flowables(markdown_text), onFirstPage=on_page, onLaterPages=on_page)
        return buf.getvalue()
    except Exception as exc:
        raise AppError("PDF generation failed. Try the Markdown export instead.", code="pdf_failed") from exc
