from __future__ import annotations

"""Background ATL Excel import: row-wise upsert with persisted progress."""
import os
from io import BytesIO
from typing import Any, Dict, List, Optional

import pandas as pd
from pydantic import ValidationError
from sqlalchemy import update

from app.constants.atl_excel_import import ATL_EXCEL_COLUMN_MAPPING
from app.database import AsyncSessionLocal
from app.models.aircraft_techinical_log import AircraftTechnicalLog
from app.models.atl_excel_import_job import AtlExcelImportJob
from app.repository.excel_import import normalize_unique_fields, upsert_validated_row, validated_to_dict
from app.schemas.aircraft_technical_log_schema import AircraftTechnicalLogImportSchema
from app.services.excel_import.hooks.atl import AtlImportHook
from app.services.excel_import.parsers import make_hashable
from app.services.excel_import.reader import normalize_column_mapping
from app.services.excel_import.row_builder import (
    build_row_for_schema,
    format_row_error,
    schema_field_names,
)

MODEL = AircraftTechnicalLog
SCHEMA = AircraftTechnicalLogImportSchema
UNIQUE_FIELDS = ["aircraft_fk", "sequence_no", "atl_batch_fk"]
_HOOK = AtlImportHook()


def _row_signature(validated: AircraftTechnicalLogImportSchema) -> tuple:
    data = validated_to_dict(validated)
    return tuple(sorted((k, make_hashable(v)) for k, v in data.items()))


async def _commit_job(job_id: str, **values: Any) -> None:
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(AtlExcelImportJob)
            .where(AtlExcelImportJob.job_id == job_id)
            .values(**values)
        )
        await s.commit()


async def process_atl_excel_import_job(job_id: str) -> None:
    temp_path: Optional[str] = None
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

        with open(temp_path, "rb") as fh:
            raw = fh.read()
        df = pd.read_excel(BytesIO(raw))
        df.columns = df.columns.str.strip().str.lower()
        mapping = normalize_column_mapping(ATL_EXCEL_COLUMN_MAPPING)
        df = df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})
        df = df.where(pd.notnull(df), None)

        if "sequence_no" not in df.columns:
            await _commit_job(
                job_id,
                status="FAILED",
                message="Missing required column: sequence_no (or a header alias such as 'Sequence No').",
                total_rows=0,
                processed_rows=0,
            )
            return

        records = _HOOK.preprocess_records(df.to_dict(orient="records"))
        total = len(records)
        fields = normalize_unique_fields(UNIQUE_FIELDS)
        schema_fields = schema_field_names(SCHEMA)
        inject_fields = {"aircraft_fk": aircraft_fk, "atl_batch_fk": atl_batch_fk}

        await _commit_job(
            job_id,
            status="PROCESSING",
            message="Import in progress",
            total_rows=total,
            processed_rows=0,
            failed_rows=0,
            errors=[],
        )

        seen_sigs: set = set()
        errors: List[Dict[str, Any]] = []
        failed = 0

        async with AsyncSessionLocal() as session:
            with session.no_autoflush:
                for idx, row in enumerate(records):
                    excel_row = idx + 2
                    try:
                        row_data = build_row_for_schema(
                            row,
                            schema_fields=schema_fields,
                            inject_fields=inject_fields,
                            hook=_HOOK,
                        )
                        validated = SCHEMA(**row_data)
                    except (ValidationError, Exception) as exc:
                        failed += 1
                        errors.append({"row": excel_row, "error": format_row_error(exc)})
                        await _commit_job(
                            job_id,
                            processed_rows=idx + 1,
                            failed_rows=failed,
                            errors=list(errors),
                            message=f"Row {excel_row}: validation error",
                        )
                        continue

                    sig = _row_signature(validated)
                    if sig in seen_sigs:
                        await _commit_job(
                            job_id,
                            processed_rows=idx + 1,
                            failed_rows=failed,
                            errors=list(errors),
                            message=f"Skipped duplicate row content at sheet row {excel_row}",
                        )
                        continue
                    seen_sigs.add(sig)

                    try:
                        await upsert_validated_row(
                            session,
                            MODEL,
                            validated,
                            fields,
                            _HOOK,
                            audit_account_id=audit_account_id,
                        )
                        await session.commit()
                    except ValueError as exc:
                        await session.rollback()
                        failed += 1
                        errors.append({"row": excel_row, "error": str(exc)})
                        await _commit_job(
                            job_id,
                            processed_rows=idx + 1,
                            failed_rows=failed,
                            errors=list(errors),
                            message=f"Row {excel_row}: duplicate",
                        )
                        continue
                    except Exception as exc:
                        await session.rollback()
                        failed += 1
                        errors.append({"row": excel_row, "error": str(exc)})

                    await _commit_job(
                        job_id,
                        processed_rows=idx + 1,
                        failed_rows=failed,
                        errors=list(errors),
                        message=f"Processed {idx + 1} of {total}",
                    )

        await _commit_job(
            job_id,
            status="COMPLETED",
            message="Import completed",
            processed_rows=total,
            failed_rows=failed,
            errors=list(errors),
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
