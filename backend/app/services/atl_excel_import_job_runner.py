from __future__ import annotations

"""Background ATL Excel import: validate all rows, then bulk upsert in one transaction."""
import os
import time
from io import BytesIO
from typing import Any, Dict, Optional

import pandas as pd
from sqlalchemy import update

from app.constants.atl_excel_import import ATL_EXCEL_COLUMN_MAPPING
from app.database import AsyncSessionLocal
from app.models.atl_excel_import_job import AtlExcelImportJob
from app.services.atl_import_service import run_atl_import
from app.services.excel_import.reader import normalize_column_mapping

from app.services.atl_excel_import_summary_codec import encode_message_with_summary

# Background job recommended for large files (see LARGE_IMPORT_ROW_THRESHOLD).
LARGE_IMPORT_ROW_THRESHOLD = 500


async def _commit_job(job_id: str, **values: Any) -> None:
    summary = values.pop("import_summary", None)
    if isinstance(summary, dict):
        values["message"] = encode_message_with_summary(
            str(values.get("message") or ""),
            summary,
        )
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(AtlExcelImportJob)
            .where(AtlExcelImportJob.job_id == job_id)
            .values(**values)
        )
        await s.commit()


def _read_atl_spreadsheet(path: str) -> tuple[list[dict], int, bool]:
    """Read Excel file into record dicts; return (records, source_row_count, has_sequence_no)."""
    with open(path, "rb") as fh:
        raw = fh.read()
    df = pd.read_excel(BytesIO(raw))
    df.columns = df.columns.str.strip().str.lower()
    mapping = normalize_column_mapping(ATL_EXCEL_COLUMN_MAPPING)
    df = df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})
    df = df.where(pd.notnull(df), None)
    has_sequence_no = "sequence_no" in df.columns
    source_row_count = len(df)
    records = df.to_dict(orient="records")
    return records, source_row_count, has_sequence_no


async def process_atl_excel_import_job(job_id: str) -> None:
    temp_path: Optional[str] = None
    started = time.perf_counter()
    try:
        async with AsyncSessionLocal() as meta:
            job = await meta.get(AtlExcelImportJob, job_id)
            if not job:
                return
            temp_path = job.temp_file_path
            aircraft_fk = job.aircraft_fk
            atl_batch_fk = job.atl_batch_fk
            audit_account_id = job.started_by

        if not temp_path or not os.path.isfile(temp_path):
            await _commit_job(
                job_id,
                status="FAILED",
                message="Temporary upload file is missing or was already removed.",
            )
            return

        records, source_row_count, has_sequence_no = _read_atl_spreadsheet(temp_path)
        total = len(records)
        inject_fields = {"aircraft_fk": aircraft_fk, "atl_batch_fk": atl_batch_fk}

        if not has_sequence_no:
            await _commit_job(
                job_id,
                status="FAILED",
                message="Missing required column: sequence_no (or a header alias such as 'Sequence No').",
                total_rows=0,
                processed_rows=0,
            )
            return

        await _commit_job(
            job_id,
            status="PROCESSING",
            message="Validating import file",
            total_rows=total,
            processed_rows=0,
            failed_rows=0,
            errors=[],
        )

        async with AsyncSessionLocal() as session:
            result = await run_atl_import(
                session,
                records,
                inject_fields=inject_fields,
                audit_account_id=audit_account_id,
                source_row_count=source_row_count,
            )

        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        summary = {
            "total_rows": result.get("total_rows", total),
            "imported_rows": result.get("imported_rows", 0),
            "inserted": result.get("inserted", 0),
            "updated": result.get("updated", 0),
            "skipped_rows": result.get("skipped_rows", 0),
            "processing_time_ms": result.get("processing_time_ms", elapsed_ms),
        }

        if result["status"] == "failed" and result.get("errors"):
            failed_row_count = len({e["row"] for e in result["errors"] if e.get("row")})
            await _commit_job(
                job_id,
                status="VALIDATION_FAILED",
                message=result.get(
                    "message",
                    "The file contains validation errors. No records were imported.",
                ),
                total_rows=summary["total_rows"],
                processed_rows=0,
                failed_rows=failed_row_count,
                errors=result["errors"],
                import_summary=summary,
            )
            return

        if result["status"] != "success":
            await _commit_job(
                job_id,
                status="FAILED",
                message=result.get("message", "Import failed."),
                total_rows=summary["total_rows"],
                processed_rows=0,
                failed_rows=summary["total_rows"],
                errors=result.get("errors", []),
                import_summary=summary,
            )
            return

        await _commit_job(
            job_id,
            status="COMPLETED",
            message=(
                f"Import completed: {summary['imported_rows']} row(s) "
                f"({summary['inserted']} inserted, {summary['updated']} updated) "
                f"in {summary['processing_time_ms']}ms."
            ),
            processed_rows=summary["imported_rows"],
            failed_rows=0,
            errors=[],
            import_summary=summary,
        )

    except Exception as e:
        await _commit_job(
            job_id,
            status="FAILED",
            message=str(e)[:4000],
        )
    finally:
        if temp_path:
            try:
                if os.path.isfile(temp_path):
                    os.unlink(temp_path)
            except OSError:
                pass
            try:
                await _commit_job(job_id, temp_file_path=None)
            except Exception:
                pass
