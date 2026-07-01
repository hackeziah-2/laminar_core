"""Build ATL import job progress payloads for GET /import-progress."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.models.atl_excel_import_job import AtlExcelImportJob
from app.schemas.atl_excel_import_job_schema import AtlImportSummaryResponse
from app.services.atl_excel_import_summary_codec import (
    decode_summary_from_message,
    display_message,
)
from app.services.excel_import.validation_errors import format_error_report_markdown

_TERMINAL_STATUSES = frozenset({"COMPLETED", "VALIDATION_FAILED", "FAILED"})


def compute_import_progress(job: AtlExcelImportJob) -> float:
    """Return 0–100 progress; terminal jobs always report 100%."""
    if job.status in _TERMINAL_STATUSES:
        return 100.0
    if job.status == "PENDING":
        return 0.0
    total = job.total_rows or 0
    if total <= 0:
        return 0.0
    processed = min(job.processed_rows or 0, total)
    return round(100.0 * processed / total, 2)


def _summary_from_job(job: AtlExcelImportJob) -> Optional[AtlImportSummaryResponse]:
    raw = decode_summary_from_message(job.message)
    if raw is None:
        raw = getattr(job, "import_summary", None)
    if isinstance(raw, dict):
        return AtlImportSummaryResponse(
            total_rows=int(raw.get("total_rows", job.total_rows or 0)),
            imported_rows=int(raw.get("imported_rows", 0)),
            inserted=int(raw.get("inserted", 0)),
            updated=int(raw.get("updated", 0)),
            skipped_rows=int(raw.get("skipped_rows", 0)),
            processing_time_ms=raw.get("processing_time_ms"),
        )

    if job.status == "COMPLETED":
        imported = job.processed_rows or 0
        return AtlImportSummaryResponse(
            total_rows=job.total_rows or 0,
            imported_rows=imported,
            inserted=imported,
            updated=0,
            skipped_rows=0,
        )

    if job.status == "VALIDATION_FAILED":
        return AtlImportSummaryResponse(
            total_rows=job.total_rows or 0,
            imported_rows=0,
            inserted=0,
            updated=0,
            skipped_rows=0,
        )

    return None


def build_import_progress_payload(job: AtlExcelImportJob) -> Dict[str, Any]:
    errors: List[Dict[str, Any]] = job.errors if isinstance(job.errors, list) else []
    summary = _summary_from_job(job)
    error_report = None
    if errors and job.status in ("VALIDATION_FAILED", "FAILED"):
        error_report = format_error_report_markdown(errors)

    payload: Dict[str, Any] = {
        "job_id": job.job_id,
        "progress": compute_import_progress(job),
        "status": job.status,
        "message": display_message(job.message),
        "total_rows": job.total_rows or 0,
        "processed_rows": job.processed_rows or 0,
        "failed_rows": job.failed_rows or 0,
        "errors": errors,
        "error_report": error_report,
        "summary": summary,
        "imported_rows": summary.imported_rows if summary else 0,
        "inserted": summary.inserted if summary else 0,
        "updated": summary.updated if summary else 0,
        "skipped_rows": summary.skipped_rows if summary else 0,
        "processing_time_ms": summary.processing_time_ms if summary else None,
    }
    return payload
