"""Optimized ATL import: validate all rows, then bulk persist in one transaction."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.atl_import import bulk_upsert_atl_import_rows
from app.services.atl_import_references import (
    AtlImportReferences,
    collect_account_ids_from_validated_rows,
    load_atl_import_references,
)
from app.services.atl_import_validation import (
    preprocess_atl_records,
    validate_account_reference_fields,
    validate_atl_schema_and_duplicates,
)
from app.services.excel_import.hooks.atl import AtlImportHook
from app.services.excel_import.validation_errors import format_error_report_markdown

_HOOK = AtlImportHook()


@dataclass
class AtlImportSummary:
    total_rows: int
    imported_rows: int
    inserted: int
    updated: int
    skipped_rows: int
    processing_time_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _count_insert_update(
    validated_rows: List[Tuple[int, Any]],
    references: AtlImportReferences,
) -> Tuple[int, int]:
    inserted = 0
    updated = 0
    for _, validated in validated_rows:
        if references.is_existing(validated.sequence_no):
            updated += 1
        else:
            inserted += 1
    return inserted, updated


def _failure_result(
    *,
    errors: List[Dict[str, Any]],
    total_rows: int,
    skipped_rows: int,
    processing_time_ms: float,
    inserted: int = 0,
    updated: int = 0,
) -> Dict[str, Any]:
    return {
        "status": "failed",
        "inserted": inserted,
        "updated": updated,
        "errors": errors,
        "message": "The file contains validation errors. No records were imported.",
        "error_report": format_error_report_markdown(errors) if errors else None,
        "total_rows": total_rows,
        "imported_rows": 0,
        "skipped_rows": skipped_rows,
        "processing_time_ms": round(processing_time_ms, 2),
    }


async def run_atl_import(
    session: AsyncSession,
    records: List[Dict[str, Any]],
    *,
    inject_fields: Dict[str, Any],
    audit_account_id: Optional[int] = None,
    dry_run: bool = False,
    source_row_count: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Validate every row, then bulk upsert in a single transaction when valid.

    Reference data (existing ATL rows, account FKs) is loaded once — never per row.
    """
    started = time.perf_counter()
    records = preprocess_atl_records(records)
    total_rows = len(records)
    skipped_rows = max(0, (source_row_count or total_rows) - total_rows)

    validated_rows, errors = validate_atl_schema_and_duplicates(
        records,
        inject_fields=inject_fields,
    )
    if errors:
        await session.rollback()
        return _failure_result(
            errors=errors,
            total_rows=total_rows,
            skipped_rows=skipped_rows,
            processing_time_ms=(time.perf_counter() - started) * 1000,
        )

    aircraft_fk = int(inject_fields["aircraft_fk"])
    atl_batch_fk = int(inject_fields["atl_batch_fk"])
    account_ids = collect_account_ids_from_validated_rows(validated_rows)
    references = await load_atl_import_references(
        session,
        aircraft_fk=aircraft_fk,
        atl_batch_fk=atl_batch_fk,
        account_ids=account_ids,
    )
    reference_errors = validate_account_reference_fields(validated_rows, references)
    if reference_errors:
        await session.rollback()
        return _failure_result(
            errors=reference_errors,
            total_rows=total_rows,
            skipped_rows=skipped_rows,
            processing_time_ms=(time.perf_counter() - started) * 1000,
        )

    inserted, updated = _count_insert_update(validated_rows, references)
    summary = AtlImportSummary(
        total_rows=total_rows,
        imported_rows=inserted + updated,
        inserted=inserted,
        updated=updated,
        skipped_rows=skipped_rows,
        processing_time_ms=round((time.perf_counter() - started) * 1000, 2),
    )

    if dry_run:
        return {
            "status": "dry-run",
            "inserted": inserted,
            "updated": updated,
            "errors": [],
            "message": None,
            "error_report": None,
            **summary.to_dict(),
        }

    try:
        with session.no_autoflush:
            persisted_inserted, persisted_updated = await bulk_upsert_atl_import_rows(
                session,
                validated_rows,
                references=references,
                audit_account_id=audit_account_id,
            )
            from app.core.atl_derived_times import backfill_atl_auto_fields_for_scope

            await backfill_atl_auto_fields_for_scope(
                session,
                aircraft_fk,
                atl_batch_fk=atl_batch_fk,
            )
        await session.commit()
        summary.inserted = persisted_inserted
        summary.updated = persisted_updated
        summary.imported_rows = persisted_inserted + persisted_updated
        summary.processing_time_ms = round((time.perf_counter() - started) * 1000, 2)

        return {
            "status": "success",
            "inserted": summary.inserted,
            "updated": summary.updated,
            "errors": [],
            **summary.to_dict(),
        }
    except IntegrityError:
        await session.rollback()
        raise
    except Exception as exc:
        await session.rollback()
        return {
            "status": "failed",
            "inserted": 0,
            "updated": 0,
            "errors": [
                {
                    "row": 0,
                    "column": "Import",
                    "value": "",
                    "error": f"Import failed and was rolled back: {exc}",
                }
            ],
            "message": f"Import failed and was rolled back: {exc}",
            **summary.to_dict(),
            "imported_rows": 0,
        }
