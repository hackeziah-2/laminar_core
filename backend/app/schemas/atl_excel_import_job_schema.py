from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AtlExcelImportStartResponse(BaseModel):
    job_id: str
    status: str
    message: str


class AtlExcelImportValidationError(BaseModel):
    row: int
    column: str
    value: str
    error: str
    expected: Optional[str] = None


class AtlImportSummaryResponse(BaseModel):
    total_rows: int = 0
    imported_rows: int = 0
    inserted: int = 0
    updated: int = 0
    skipped_rows: int = 0
    processing_time_ms: Optional[float] = None


class AtlExcelImportProgressResponse(BaseModel):
    job_id: str
    progress: float = Field(..., description="0–100; terminal jobs (completed/failed) return 100")
    status: str
    message: Optional[str] = None
    total_rows: int = 0
    processed_rows: int = Field(
        0,
        description="Rows imported on success; 0 when validation failed or still processing",
    )
    failed_rows: int = 0
    imported_rows: int = Field(0, description="Rows successfully imported (insert + update)")
    inserted: int = 0
    updated: int = 0
    skipped_rows: int = Field(
        0,
        description="Source rows merged as continuation lines (not imported as separate ATLs)",
    )
    processing_time_ms: Optional[float] = None
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    error_report: Optional[str] = Field(
        None,
        description="Markdown table of validation errors when status is VALIDATION_FAILED or FAILED",
    )
    summary: Optional[AtlImportSummaryResponse] = Field(
        None,
        description="Import totals and timing (duplicate of top-level summary fields)",
    )
