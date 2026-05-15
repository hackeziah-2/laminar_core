from __future__ import annotations

"""Background ATL Excel import: row-wise upsert with persisted progress."""
import os
from io import BytesIO
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import select, update

from app.constants.atl_excel_import import ATL_EXCEL_COLUMN_MAPPING
from app.database import AsyncSessionLocal, set_audit_fields
from app.models.aircraft_techinical_log import AircraftTechnicalLog
from app.models.atl_excel_import_job import AtlExcelImportJob
from app.repository.aircraft_technical_log import _replace_atl_component_parts
from app.schemas.aircraft_technical_log_schema import AircraftTechnicalLogImportSchema
from app.services.atl_import_normalize import merge_atl_continuation_records, normalize_atl_import_row
from app.services.import_data_excel import (
    _make_hashable,
    _model_column_names,
    _normalize_import_nature_of_flight,
    _normalize_unique_fields,
    _parse_import_origin_date,
    _schema_field_names,
)

MODEL = AircraftTechnicalLog
SCHEMA = AircraftTechnicalLogImportSchema
UNIQUE_FIELDS = ["aircraft_fk", "sequence_no", "atl_batch_fk"]


def _row_for_schema(
    row: Dict[str, Any],
    inject_fields: Dict[str, Any],
    schema_fields: set,
) -> Dict[str, Any]:
    merged = {**row, **inject_fields}
    normalize_atl_import_row(merged)
    out: Dict[str, Any] = {}
    for k in schema_fields:
        if k not in merged:
            continue
        val = merged[k]
        if k == "origin_date":
            val = _parse_import_origin_date(val)
        elif k == "nature_of_flight":
            val = _normalize_import_nature_of_flight(val)
        out[k] = val
    return out


def _stmt_lookup(validated: AircraftTechnicalLogImportSchema, fields: List[str]):
    stmt = select(MODEL)
    for f in fields:
        stmt = stmt.where(getattr(MODEL, f) == getattr(validated, f))
    return stmt


async def _unique_field_taken(
    session,
    validated: AircraftTechnicalLogImportSchema,
    fields: List[str],
    exclude_id: Optional[int] = None,
):
    stmt = select(MODEL)
    for f in fields:
        stmt = stmt.where(getattr(MODEL, f) == getattr(validated, f, None))
    if exclude_id and hasattr(MODEL, "id"):
        stmt = stmt.where(MODEL.id != exclude_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def _row_signature(validated: AircraftTechnicalLogImportSchema):
    d = validated.dict()
    return tuple(sorted((k, _make_hashable(v)) for k, v in d.items()))


async def _commit_job(job_id: str, **values: Any) -> None:
    async with AsyncSessionLocal() as s:
        await s.execute(update(AtlExcelImportJob).where(AtlExcelImportJob.job_id == job_id).values(**values))
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
        cm = {k.strip().lower(): v.strip().lower() for k, v in ATL_EXCEL_COLUMN_MAPPING.items()}
        df = df.rename(columns={k: v for k, v in cm.items() if k in df.columns})
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

        records = df.to_dict(orient="records")
        records = merge_atl_continuation_records(records)
        total = len(records)

        await _commit_job(
            job_id,
            status="PROCESSING",
            message="Import in progress",
            total_rows=total,
            processed_rows=0,
            failed_rows=0,
            errors=[],
        )

        inject_fields = {"aircraft_fk": aircraft_fk, "atl_batch_fk": atl_batch_fk}
        fields = _normalize_unique_fields(UNIQUE_FIELDS)
        schema_fields = _schema_field_names(SCHEMA)
        model_columns = _model_column_names(MODEL)
        seen_sigs: set = set()
        errors: List[Dict[str, Any]] = []
        failed = 0

        async with AsyncSessionLocal() as session:
            with session.no_autoflush:
                for idx, row in enumerate(records):
                    excel_row = idx + 2
                    try:
                        row_data = _row_for_schema(row, inject_fields, schema_fields)
                        validated = SCHEMA(**row_data)
                    except Exception as e:
                        failed += 1
                        errors.append({"row": excel_row, "error": str(e)})
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
                        result = await session.execute(_stmt_lookup(validated, fields))
                        existing = result.scalar_one_or_none()

                        if existing:
                            conflict = await _unique_field_taken(
                                session, validated, fields, exclude_id=existing.id
                            )
                            if conflict:
                                failed += 1
                                errors.append(
                                    {"row": excel_row, "error": "Duplicate unique field value"}
                                )
                                await session.rollback()
                                await _commit_job(
                                    job_id,
                                    processed_rows=idx + 1,
                                    failed_rows=failed,
                                    errors=list(errors),
                                    message=f"Row {excel_row}: duplicate",
                                )
                                continue

                            data = validated.dict()
                            for key in model_columns:
                                if key in data:
                                    setattr(existing, key, data[key])

                            if hasattr(existing, "is_deleted") and existing.is_deleted:
                                existing.is_deleted = False

                            if audit_account_id is not None:
                                await set_audit_fields(
                                    existing, audit_account_id, is_create=False
                                )

                            parts = getattr(validated, "component_parts", None)
                            if parts is not None:
                                await _replace_atl_component_parts(
                                    session=session,
                                    atl_id=existing.id,
                                    component_parts=list(parts),
                                    audit_account_id=audit_account_id,
                                )
                        else:
                            conflict = await _unique_field_taken(session, validated, fields)
                            if conflict:
                                failed += 1
                                errors.append(
                                    {"row": excel_row, "error": "Duplicate unique field value"}
                                )
                                await session.rollback()
                                await _commit_job(
                                    job_id,
                                    processed_rows=idx + 1,
                                    failed_rows=failed,
                                    errors=list(errors),
                                    message=f"Row {excel_row}: duplicate",
                                )
                                continue

                            data = validated.dict()
                            payload = {k: data[k] for k in model_columns if k in data}
                            obj = MODEL(**payload)
                            session.add(obj)
                            if audit_account_id is not None:
                                await set_audit_fields(obj, audit_account_id, is_create=True)

                            await session.flush()
                            parts = getattr(validated, "component_parts", None)
                            if parts is not None:
                                await _replace_atl_component_parts(
                                    session=session,
                                    atl_id=obj.id,
                                    component_parts=list(parts),
                                    audit_account_id=audit_account_id,
                                )

                        await session.commit()

                    except Exception as e:
                        await session.rollback()
                        failed += 1
                        errors.append({"row": excel_row, "error": str(e)})

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
