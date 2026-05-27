from datetime import date, datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Sequence

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A3, A4, LETTER, landscape, portrait
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def generate_pdf_report(title, headers, data, header_color="#1f6fff"):
    pdf_stream = BytesIO()

    pdf = SimpleDocTemplate(
        pdf_stream,
        pagesize=landscape(A4),
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=20,   
        title="Aircraft Report",
        author="Laminar",
    )

    table_data = [headers] + data

    # Column widths (adjusted for readability)
    col_widths = [
        1.2 * inch,  # AC REG
        1.6 * inch,  # AIRCRAFT TYPE
        1.6 * inch,  # MODEL
        1.6 * inch,  # MSN
        2.8 * inch,  # BASE LOCATION (long text)
        1.2 * inch,  # STATUS
        1.2 * inch,  # CREATED AT
    ]

    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(header_color)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),

        # Body
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),

        # Padding
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))

    pdf.build([table])
    pdf_stream.seek(0)
    return pdf_stream


# ---------------------------------------------------------------------------
# Enterprise dynamic PDF report
# ---------------------------------------------------------------------------

_PAGE_SIZES = {"a4": A4, "a3": A3, "letter": LETTER}

_STATUS_TINTS = {
    "active":       ("#065F46", "#D1FAE5"),
    "operational":  ("#065F46", "#D1FAE5"),
    "available":    ("#065F46", "#D1FAE5"),
    "valid":        ("#065F46", "#D1FAE5"),
    "ok":           ("#065F46", "#D1FAE5"),
    "approved":     ("#065F46", "#D1FAE5"),
    "completed":    ("#065F46", "#D1FAE5"),
    "compliant":    ("#065F46", "#D1FAE5"),

    "pending":      ("#92400E", "#FEF3C7"),
    "warning":      ("#92400E", "#FEF3C7"),
    "due-soon":     ("#92400E", "#FEF3C7"),
    "maintenance":  ("#92400E", "#FEF3C7"),
    "in-progress":  ("#92400E", "#FEF3C7"),

    "inactive":     ("#1F2937", "#E5E7EB"),
    "draft":        ("#1F2937", "#E5E7EB"),
    "archived":     ("#1F2937", "#E5E7EB"),

    "expired":      ("#7F1D1D", "#FEE2E2"),
    "overdue":      ("#7F1D1D", "#FEE2E2"),
    "failed":       ("#7F1D1D", "#FEE2E2"),
    "rejected":     ("#7F1D1D", "#FEE2E2"),
    "grounded":     ("#7F1D1D", "#FEE2E2"),
    "non-compliant":("#7F1D1D", "#FEE2E2"),
}


def _humanize_module_name(module_name: str) -> str:
    """Turn 'aircraft_technical_log' / 'fleet-daily-update' into 'Aircraft Technical Log'."""
    if not module_name:
        return "Report"
    cleaned = str(module_name).replace("-", " ").replace("_", " ").strip()
    return " ".join(part.capitalize() for part in cleaned.split() if part) or "Report"


def _format_cell_value(value: Any, fmt: Optional[str]) -> str:
    """Render a value for a PDF cell using an optional format hint."""
    if value is None or value == "":
        return ""

    fmt_norm = (fmt or "").strip().lower()

    if isinstance(value, bool):
        return "Yes" if value else "No"

    if fmt_norm in {"date", "datetime"}:
        if isinstance(value, (datetime, date)):
            dt = value
        else:
            try:
                dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                return str(value)
        if fmt_norm == "date" or not isinstance(dt, datetime):
            return dt.strftime("%Y-%m-%d") if isinstance(dt, (date, datetime)) else str(value)
        return dt.strftime("%Y-%m-%d %H:%M")

    if fmt_norm == "boolean":
        return "Yes" if bool(value) else "No"

    if fmt_norm == "currency":
        try:
            return f"{float(value):,.2f}"
        except (TypeError, ValueError):
            return str(value)

    if fmt_norm == "number":
        try:
            num = float(value)
            return f"{int(num):,}" if num.is_integer() else f"{num:,.2f}"
        except (TypeError, ValueError):
            return str(value)

    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d %H:%M") if isinstance(value, datetime) else value.strftime("%Y-%m-%d")

    if isinstance(value, (list, tuple, set)):
        return ", ".join(_format_cell_value(v, None) for v in value if v not in (None, ""))

    if isinstance(value, dict):
        for key in ("name", "label", "title", "value", "registration"):
            if key in value and value[key] not in (None, ""):
                return str(value[key])
        return ", ".join(f"{k}: {v}" for k, v in value.items() if v not in (None, ""))

    return str(value)


def _derive_columns(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Auto-derive column specs from the first non-empty row, preserving insertion order."""
    seen: List[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key in row.keys():
            if key not in seen:
                seen.append(key)
    return [
        {"key": k, "label": _humanize_module_name(k), "align": "left", "format": None}
        for k in seen
    ]


def _column_widths(
    columns: Sequence[Dict[str, Any]],
    available_width: float,
    formatted_rows: Sequence[Sequence[str]],
) -> List[float]:
    """Compute column widths: explicit > content-weighted > equal split, capped to available width."""
    n = len(columns)
    if n == 0:
        return []

    explicit_total = 0.0
    widths: List[Optional[float]] = []
    for col in columns:
        width_in = col.get("width")
        try:
            w = float(width_in) * inch if width_in not in (None, "") else None
        except (TypeError, ValueError):
            w = None
        widths.append(w)
        if w is not None:
            explicit_total += w

    remaining = max(available_width - explicit_total, 0.0)
    auto_indices = [i for i, w in enumerate(widths) if w is None]

    if auto_indices:
        weights: List[float] = []
        for idx in auto_indices:
            label_len = len(str(columns[idx].get("label") or columns[idx].get("key") or ""))
            sample_lens = [len(row[idx]) for row in formatted_rows[:20] if idx < len(row)]
            avg_len = sum(sample_lens) / len(sample_lens) if sample_lens else label_len
            weights.append(max(label_len, avg_len, 6.0))

        weight_total = sum(weights) or float(len(auto_indices))
        per_unit = remaining / weight_total
        for idx, weight in zip(auto_indices, weights):
            widths[idx] = max(weight * per_unit, 0.6 * inch)

    final = [w if w is not None else (available_width / n) for w in widths]

    total = sum(final)
    if total > available_width and total > 0:
        scale = available_width / total
        final = [w * scale for w in final]
    return final


def _build_header_footer(
    *,
    module_label: str,
    title: str,
    subtitle: Optional[str],
    company_name: str,
    header_color: str,
    footer_note: Optional[str],
    generated_at: datetime,
):
    """Return a (on_page) callable for BaseDocTemplate to draw the branded header / footer."""
    header_color_obj = colors.HexColor(header_color)
    accent_color = colors.HexColor("#0F172A")
    muted_color = colors.HexColor("#6B7280")
    divider_color = colors.HexColor("#E5E7EB")

    def on_page(canvas: pdf_canvas.Canvas, doc: BaseDocTemplate) -> None:
        canvas.saveState()
        page_w, page_h = doc.pagesize
        margin = doc.leftMargin

        band_h = 22 * mm
        canvas.setFillColor(header_color_obj)
        canvas.rect(0, page_h - band_h, page_w, band_h, stroke=0, fill=1)

        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 14)
        canvas.drawString(margin, page_h - band_h + 12 * mm, company_name)

        canvas.setFont("Helvetica", 9)
        canvas.drawString(margin, page_h - band_h + 6 * mm, f"{module_label} Report")

        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(
            page_w - margin,
            page_h - band_h + 12 * mm,
            title,
        )
        if subtitle:
            canvas.setFont("Helvetica-Oblique", 8)
            canvas.drawRightString(
                page_w - margin,
                page_h - band_h + 6 * mm,
                subtitle[:120],
            )

        footer_y = 12 * mm
        canvas.setStrokeColor(divider_color)
        canvas.setLineWidth(0.5)
        canvas.line(margin, footer_y + 6 * mm, page_w - margin, footer_y + 6 * mm)

        canvas.setFillColor(muted_color)
        canvas.setFont("Helvetica", 8)
        generated_str = generated_at.strftime("Generated %Y-%m-%d %H:%M")
        canvas.drawString(margin, footer_y, generated_str)

        if footer_note:
            canvas.drawCentredString(page_w / 2.0, footer_y, footer_note[:140])

        canvas.setFillColor(accent_color)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawRightString(
            page_w - margin,
            footer_y,
            f"Page {doc.page}",
        )
        canvas.restoreState()

    return on_page


def generate_enterprise_pdf_report(
    *,
    module_name: str,
    data: Sequence[Dict[str, Any]],
    columns: Optional[Sequence[Dict[str, Any]]] = None,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    orientation: str = "landscape",
    page_size: str = "a4",
    header_color: str = "#1E3A8A",
    company_name: str = "Laminar Aviation",
    footer_note: Optional[str] = None,
    generated_at: Optional[datetime] = None,
) -> BytesIO:
    """Build a polished, enterprise-styled PDF report from arbitrary tabular data.

    The function is module-agnostic: pass any list of dicts and (optionally) a column
    spec to fully control labels, ordering, formatting and alignment. When columns is
    omitted, the column set is derived from the keys of the first row.
    """
    module_label = _humanize_module_name(module_name)
    resolved_title = title or f"{module_label} Report"
    generated_at = generated_at or datetime.now()

    selected_size = _PAGE_SIZES.get((page_size or "a4").strip().lower(), A4)
    page = landscape(selected_size) if (orientation or "landscape").lower() == "landscape" else portrait(selected_size)

    column_specs: List[Dict[str, Any]] = [dict(c) for c in (columns or [])] or _derive_columns(data)

    rows_dicts: List[Dict[str, Any]] = [r for r in (data or []) if isinstance(r, dict)]
    formatted_rows: List[List[str]] = [
        [_format_cell_value(row.get(col["key"]), col.get("format")) for col in column_specs]
        for row in rows_dicts
    ]

    pdf_stream = BytesIO()

    side_margin = 14 * mm
    top_margin = 30 * mm
    bottom_margin = 22 * mm

    doc = BaseDocTemplate(
        pdf_stream,
        pagesize=page,
        leftMargin=side_margin,
        rightMargin=side_margin,
        topMargin=top_margin,
        bottomMargin=bottom_margin,
        title=resolved_title,
        author=company_name,
        subject=f"{module_label} report generated by {company_name}",
    )

    frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
        id="content",
    )
    on_page = _build_header_footer(
        module_label=module_label,
        title=resolved_title,
        subtitle=subtitle,
        company_name=company_name,
        header_color=header_color,
        footer_note=footer_note,
        generated_at=generated_at,
    )
    doc.addPageTemplates([PageTemplate(id="enterprise", frames=[frame], onPage=on_page)])

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=2,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        textColor=colors.HexColor("#475569"),
        spaceAfter=10,
    )
    meta_style = ParagraphStyle(
        "ReportMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=colors.HexColor("#64748B"),
        spaceAfter=12,
    )
    cell_base_style = ParagraphStyle(
        "Cell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=10.5,
        textColor=colors.HexColor("#111827"),
        wordWrap="CJK",
    )
    header_cell_style = ParagraphStyle(
        "HeaderCell",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.white,
        alignment=TA_CENTER,
        wordWrap="CJK",
    )

    alignment_map = {"left": TA_LEFT, "center": TA_CENTER, "right": TA_RIGHT}

    story: List[Any] = []
    story.append(Paragraph(resolved_title, title_style))
    if subtitle:
        story.append(Paragraph(subtitle, subtitle_style))
    story.append(
        Paragraph(
            f"Module: <b>{module_label}</b> &nbsp;|&nbsp; "
            f"Records: <b>{len(rows_dicts)}</b> &nbsp;|&nbsp; "
            f"Generated: <b>{generated_at.strftime('%Y-%m-%d %H:%M')}</b>",
            meta_style,
        )
    )

    if not column_specs:
        story.append(Paragraph("No columns to display.", subtitle_style))
        doc.build(story)
        pdf_stream.seek(0)
        return pdf_stream

    header_paragraphs = [
        Paragraph(str(col.get("label") or col.get("key") or ""), header_cell_style)
        for col in column_specs
    ]

    body_paragraphs: List[List[Any]] = []
    status_col_indices = [
        i for i, col in enumerate(column_specs)
        if str(col.get("key") or "").lower() in {"status", "state", "compliance_status"}
    ]
    status_cell_styles: Dict[str, ParagraphStyle] = {}

    for row_idx, row_values in enumerate(formatted_rows):
        rendered_row: List[Any] = []
        for col_idx, value in enumerate(row_values):
            col = column_specs[col_idx]
            align = alignment_map.get(str(col.get("align") or "left").lower(), TA_LEFT)
            style = ParagraphStyle(
                f"Cell_{row_idx}_{col_idx}",
                parent=cell_base_style,
                alignment=align,
            )
            rendered_row.append(Paragraph(value or "&nbsp;", style))
        body_paragraphs.append(rendered_row)

    table_data = [header_paragraphs] + body_paragraphs

    available_width = doc.width
    col_widths = _column_widths(column_specs, available_width, formatted_rows)

    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    header_color_obj = colors.HexColor(header_color)
    stripe_color = colors.HexColor("#F8FAFC")
    grid_color = colors.HexColor("#E2E8F0")
    outer_color = colors.HexColor("#CBD5E1")

    style_cmds: List[Any] = [
        ("BACKGROUND", (0, 0), (-1, 0), header_color_obj),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("VALIGN", (0, 1), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 1), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#111827")),
        ("LEFTPADDING", (0, 1), (-1, -1), 6),
        ("RIGHTPADDING", (0, 1), (-1, -1), 6),
        ("TOPPADDING", (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, grid_color),
        ("BOX", (0, 0), (-1, -1), 0.6, outer_color),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, header_color_obj),
    ]

    for row_idx in range(1, len(table_data)):
        if row_idx % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), stripe_color))

    for status_idx in status_col_indices:
        for body_row_idx, raw_values in enumerate(formatted_rows, start=1):
            if status_idx >= len(raw_values):
                continue
            raw_status = (raw_values[status_idx] or "").strip().lower()
            tint = _STATUS_TINTS.get(raw_status)
            if not tint:
                continue
            fg_hex, bg_hex = tint
            style_cmds.append(("BACKGROUND", (status_idx, body_row_idx), (status_idx, body_row_idx), colors.HexColor(bg_hex)))
            style_cmds.append(("TEXTCOLOR", (status_idx, body_row_idx), (status_idx, body_row_idx), colors.HexColor(fg_hex)))
            style_cmds.append(("FONTNAME", (status_idx, body_row_idx), (status_idx, body_row_idx), "Helvetica-Bold"))
            cell_style_key = f"{fg_hex}_{bg_hex}"
            badge_style = status_cell_styles.get(cell_style_key)
            if badge_style is None:
                badge_style = ParagraphStyle(
                    f"StatusBadge_{cell_style_key}",
                    parent=cell_base_style,
                    alignment=TA_CENTER,
                    fontName="Helvetica-Bold",
                    textColor=colors.HexColor(fg_hex),
                )
                status_cell_styles[cell_style_key] = badge_style
            table_data[body_row_idx][status_idx] = Paragraph(
                raw_values[status_idx] or "&nbsp;",
                badge_style,
            )

    table.setStyle(TableStyle(style_cmds))

    if not rows_dicts:
        empty_style = ParagraphStyle(
            "EmptyState",
            parent=styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=10,
            textColor=colors.HexColor("#6B7280"),
            alignment=TA_CENTER,
            spaceBefore=20,
        )
        story.append(table)
        story.append(Spacer(1, 12))
        story.append(Paragraph("No records available for this report.", empty_style))
    else:
        story.append(table)

    doc.build(story)
    pdf_stream.seek(0)
    return pdf_stream
