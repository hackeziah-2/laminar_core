"""Schemas for Excel/CSV import API responses."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ImportRowError(BaseModel):
    row: int = Field(..., description="1-based spreadsheet row (row 1 = header)")
    error: str


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

    @classmethod
    def from_service_dict(cls, data: Dict[str, Any]) -> "ExcelImportResult":
        raw_errors = data.get("errors") or []
        errors = [
            ImportRowError(**e) if isinstance(e, dict) else ImportRowError(row=0, error=str(e))
            for e in raw_errors
        ]
        return cls(
            status=data["status"],
            inserted=int(data.get("inserted", 0)),
            updated=int(data.get("updated", 0)),
            errors=errors,
        )
