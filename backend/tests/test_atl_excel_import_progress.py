"""Tests for ATL import progress API payload building."""
from __future__ import annotations

from types import SimpleNamespace

from app.services.atl_excel_import_progress import (
    build_import_progress_payload,
    compute_import_progress,
)


def _job(**kwargs):
    defaults = {
        "job_id": "test-job",
        "status": "PENDING",
        "message": None,
        "total_rows": 0,
        "processed_rows": 0,
        "failed_rows": 0,
        "errors": [],
        "import_summary": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_progress_terminal_validation_failed_is_100_percent():
    job = _job(status="VALIDATION_FAILED", total_rows=10, processed_rows=0, failed_rows=2)
    assert compute_import_progress(job) == 100.0


def test_progress_processing_uses_processed_rows():
    job = _job(status="PROCESSING", total_rows=10, processed_rows=4)
    assert compute_import_progress(job) == 40.0


def test_build_payload_validation_failed_shows_zero_imported():
    from app.services.atl_excel_import_summary_codec import encode_message_with_summary

    summary = {
        "total_rows": 5,
        "imported_rows": 0,
        "inserted": 0,
        "updated": 0,
        "skipped_rows": 0,
        "processing_time_ms": 120.5,
    }
    job = _job(
        status="VALIDATION_FAILED",
        total_rows=5,
        processed_rows=0,
        failed_rows=2,
        message=encode_message_with_summary(
            "The file contains validation errors. No records were imported.",
            summary,
        ),
        errors=[
            {
                "row": 3,
                "column": "Sequence No",
                "value": "ABC",
                "error": "Must be a numeric value.",
            }
        ],
    )
    payload = build_import_progress_payload(job)
    assert payload["status"] == "VALIDATION_FAILED"
    assert payload["progress"] == 100.0
    assert payload["imported_rows"] == 0
    assert payload["processed_rows"] == 0
    assert payload["failed_rows"] == 2
    assert payload["error_report"] is not None
    assert "Sequence No" in payload["error_report"]
    assert payload["processing_time_ms"] == 120.5


def test_build_payload_completed_uses_summary():
    from app.services.atl_excel_import_summary_codec import encode_message_with_summary

    summary = {
        "total_rows": 10,
        "imported_rows": 8,
        "inserted": 5,
        "updated": 3,
        "skipped_rows": 2,
        "processing_time_ms": 250.0,
    }
    job = _job(
        status="COMPLETED",
        total_rows=10,
        processed_rows=8,
        message=encode_message_with_summary("Import completed.", summary),
    )
    payload = build_import_progress_payload(job)
    assert payload["progress"] == 100.0
    assert payload["imported_rows"] == 8
    assert payload["inserted"] == 5
    assert payload["updated"] == 3
    assert payload["skipped_rows"] == 2
