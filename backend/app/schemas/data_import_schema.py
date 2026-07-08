"""Schemas for Excel/CSV import API responses."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ImportRowError(BaseModel):
    row: int = Field(..., description="1-based spreadsheet row (row 1 = header)")
    column: Optional[str] = Field(None, description="Spreadsheet column label")
    value: Optional[str] = Field(None, description="Invalid cell value")
    error: str = Field(..., description="Human-readable error message")
    expected: Optional[str] = Field(
        None, description="Expected format or valid values when applicable"
    )

    @classmethod
    def from_raw(cls, raw: Dict[str, Any]) -> "ImportRowError":
        if "error_legacy" in raw and "error" not in raw:
            raw = {**raw, "error": raw["error_legacy"]}
        error_text = str(raw.get("error") or raw.get("error_legacy") or "Invalid value.")
        return cls(
            row=int(raw.get("row", 0)),
            column=raw.get("column"),
            value=raw.get("value"),
            error=error_text,
            expected=raw.get("expected"),
        )


class ImportTargetInfo(BaseModel):
    """Describes a registered Excel import target (for discovery and dynamic clients)."""

    key: str
    label: str
    summary: str = ""
    rbac_module: str
    required_form_fields: List[str] = Field(default_factory=list)
    optional_form_fields: List[str] = Field(default_factory=list)
    legacy_paths: List[str] = Field(default_factory=list)


class ExcelImportResult(BaseModel):
    status: Literal["success", "failed", "dry-run"]
    inserted: int = 0
    updated: int = 0
    errors: List[ImportRowError] = Field(default_factory=list)
    message: Optional[str] = None
    error_report: Optional[str] = Field(
        None,
        description="Markdown table of validation errors when import fails validation",
    )
    total_rows: int = 0
    imported_rows: int = 0
    skipped_rows: int = 0
    processing_time_ms: Optional[float] = Field(
        None, description="Wall-clock processing time in milliseconds"
    )

    @classmethod
    def from_service_dict(cls, data: Dict[str, Any]) -> "ExcelImportResult":
        raw_errors = data.get("errors") or []
        errors = [
            ImportRowError.from_raw(e) if isinstance(e, dict) else ImportRowError(row=0, error=str(e))
            for e in raw_errors
        ]
        imported = int(data.get("imported_rows", data.get("inserted", 0) + data.get("updated", 0)))
        return cls(
            status=data["status"],
            inserted=int(data.get("inserted", 0)),
            updated=int(data.get("updated", 0)),
            errors=errors,
            message=data.get("message"),
            error_report=data.get("error_report"),
            total_rows=int(data.get("total_rows", 0)),
            imported_rows=imported,
            skipped_rows=int(data.get("skipped_rows", 0)),
            processing_time_ms=data.get("processing_time_ms"),
        )
