"""Request schemas for the dynamic, module-agnostic report generator.

Used by `POST /api/generate/{module_name_data}/reports/pdf` (and future
report formats). Designed for Pydantic v1 (the version pinned in
backend/requirements.txt).
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


_ALLOWED_ALIGN = {"left", "center", "right"}
_ALLOWED_FORMAT = {"string", "text", "date", "datetime", "number", "currency", "boolean"}
_ALLOWED_ORIENTATION = {"landscape", "portrait"}
_ALLOWED_PAGE_SIZE = {"a4", "a3", "letter"}


class ReportColumn(BaseModel):
    """Single column descriptor for a dynamic PDF/Excel report."""

    key: str = Field(..., description="Key in the data dict (e.g. 'registration').")
    label: Optional[str] = Field(
        None,
        description="Display label shown in the table header. Falls back to a humanized key.",
    )
    width: Optional[float] = Field(
        None,
        gt=0,
        description="Optional fixed column width in inches. Unset columns auto-fit.",
    )
    align: Optional[str] = Field(
        "left",
        description="Cell alignment: 'left', 'center' or 'right'.",
    )
    format: Optional[str] = Field(
        None,
        description="Optional value formatter: 'date', 'datetime', 'number', 'currency', 'boolean'.",
    )

    @validator("align")
    def _validate_align(cls, v: Optional[str]) -> str:
        if v is None:
            return "left"
        v_norm = v.strip().lower()
        if v_norm not in _ALLOWED_ALIGN:
            raise ValueError(f"align must be one of {sorted(_ALLOWED_ALIGN)}")
        return v_norm

    @validator("format")
    def _validate_format(cls, v: Optional[str]) -> Optional[str]:
        if v in (None, ""):
            return None
        v_norm = v.strip().lower()
        if v_norm not in _ALLOWED_FORMAT:
            raise ValueError(f"format must be one of {sorted(_ALLOWED_FORMAT)}")
        return v_norm


class ReportPDFRequest(BaseModel):
    """Request body for the dynamic PDF generator endpoint."""

    data: List[Dict[str, Any]] = Field(
        ...,
        description="Tabular data: list of objects keyed by column 'key'.",
    )
    columns: Optional[List[ReportColumn]] = Field(
        None,
        description="Optional explicit column spec. When omitted, columns are derived from the first row.",
    )
    title: Optional[str] = Field(
        None,
        description="Report title. Defaults to '<Module Name> Report'.",
        max_length=200,
    )
    subtitle: Optional[str] = Field(
        None,
        description="Optional subtitle / context line (e.g. filter description).",
        max_length=300,
    )
    orientation: Optional[str] = Field(
        "landscape",
        description="Page orientation: 'landscape' or 'portrait'.",
    )
    page_size: Optional[str] = Field(
        "a4",
        description="Page size: 'a4', 'a3' or 'letter'.",
    )
    header_color: Optional[str] = Field(
        "#1E3A8A",
        description="Hex color for the branded header band and table header (e.g. '#1E3A8A').",
        regex=r"^#(?:[0-9a-fA-F]{3}){1,2}$",
    )
    company_name: Optional[str] = Field(
        "Laminar Aviation",
        description="Company / tenant label shown in the page band.",
        max_length=120,
    )
    footer_note: Optional[str] = Field(
        None,
        description="Optional footer note shown centered on every page (e.g. confidentiality notice).",
        max_length=160,
    )
    filename: Optional[str] = Field(
        None,
        description="Optional download filename (without extension). Defaults to '<module>_report'.",
        max_length=120,
    )

    @validator("orientation")
    def _validate_orientation(cls, v: Optional[str]) -> str:
        if v is None or not str(v).strip():
            return "landscape"
        v_norm = v.strip().lower()
        if v_norm not in _ALLOWED_ORIENTATION:
            raise ValueError(f"orientation must be one of {sorted(_ALLOWED_ORIENTATION)}")
        return v_norm

    @validator("page_size")
    def _validate_page_size(cls, v: Optional[str]) -> str:
        if v is None or not str(v).strip():
            return "a4"
        v_norm = v.strip().lower()
        if v_norm not in _ALLOWED_PAGE_SIZE:
            raise ValueError(f"page_size must be one of {sorted(_ALLOWED_PAGE_SIZE)}")
        return v_norm
