"""Dynamic, module-agnostic report generation endpoints.

Currently exposes:
    POST /api/generate/{module_name_data}/reports/pdf

The endpoint accepts arbitrary tabular data plus an optional column spec and
returns a polished, enterprise-styled PDF stream. It can be reused across
every module (aircraft, fleet daily update, personnel compliance matrix,
ATL, etc.) without bespoke routes for each.
"""
from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Path, status
from fastapi.responses import StreamingResponse

from app.schemas.report_schema import ReportPDFRequest
from app.services.generate_report_pdf import generate_enterprise_pdf_report

router = APIRouter(prefix="/api/generate", tags=["report-generator"])


_MODULE_NAME_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,60}$")


def _safe_module_name(module_name_data: str) -> str:
    """Reject obviously unsafe module identifiers (path traversal, weird chars)."""
    if not module_name_data or not _MODULE_NAME_RE.match(module_name_data):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid module_name_data. Use letters, digits, '-' or '_' "
                "(max 60 chars), e.g. 'aircraft' or 'fleet-daily-update'."
            ),
        )
    return module_name_data


def _safe_filename(name: Optional[str], fallback: str) -> str:
    """Return a filesystem-safe filename stem (no path separators, no dots)."""
    candidate = (name or fallback).strip() or fallback
    cleaned = re.sub(r"[^A-Za-z0-9._\-]+", "_", candidate).strip("._-")
    return cleaned or fallback


@router.post(
    "/{module_name_data}/reports/pdf",
    summary="Generate a dynamic enterprise-styled PDF report for any module",
    description=(
        "Render any tabular dataset as a branded, enterprise-styled PDF. "
        "Works for every module (aircraft, ATL, fleet daily update, personnel compliance, etc.).\n\n"
        "- `module_name_data` is a free-form identifier (e.g. `aircraft`, `personnel-compliance-matrix`). "
        "It is used to title and name the file when no explicit `title`/`filename` is provided.\n"
        "- Send `data` as a list of plain objects.\n"
        "- Optionally supply `columns` to control labels, ordering, formatters and alignment. "
        "When omitted, columns are auto-derived from the first row's keys.\n"
        "- Optional: `title`, `subtitle`, `orientation`, `page_size`, `header_color`, "
        "`company_name`, `footer_note`, `filename`."
    ),
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "PDF binary stream.",
            "content": {"application/pdf": {}},
        },
        400: {"description": "Invalid module name."},
        422: {"description": "Validation error in request body."},
    },
)
def generate_module_pdf_report(
    payload: ReportPDFRequest,
    module_name_data: str = Path(
        ...,
        description="Module identifier, e.g. 'aircraft', 'fleet-daily-update', 'personnel-compliance-matrix'.",
        example="aircraft",
    ),
):
    module_name = _safe_module_name(module_name_data)

    pdf_stream = generate_enterprise_pdf_report(
        module_name=module_name,
        data=payload.data,
        columns=[col.dict() for col in payload.columns] if payload.columns else None,
        title=payload.title,
        subtitle=payload.subtitle,
        orientation=payload.orientation or "landscape",
        page_size=payload.page_size or "a4",
        header_color=payload.header_color or "#1E3A8A",
        company_name=payload.company_name or "Laminar Aviation",
        footer_note=payload.footer_note,
    )

    fallback_stem = f"{module_name.replace('-', '_').replace(' ', '_').lower()}_report"
    filename_stem = _safe_filename(payload.filename, fallback_stem)
    download_name = f"{filename_stem}.pdf"

    return StreamingResponse(
        pdf_stream,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{download_name}"',
            "X-Report-Module": module_name,
        },
    )
