"""
Generic Excel/CSV import for any SQLAlchemy model.

Use import_excel_generic() with your model, Pydantic schema, and unique field(s).
Optional: column_mapping (Excel header -> schema field), integrity_error_messages (constraint -> user message),
inject_fields (merge into each row before validation, e.g. aircraft_fk from endpoint).
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, Union

import pandas as pd
from fastapi import HTTPException, UploadFile
from io import BytesIO
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect as sa_inspect

from app.database import set_audit_fields
from app.models.fleet_daily_update import FleetDailyUpdate, FleetDailyUpdateStatusEnum
from app.models.aircraft import Aircraft

def _normalize_unique_fields(unique_fields: Union[str, List[str]]) -> List[str]:
    """Accept a single field name or a list of field names."""
    if isinstance(unique_fields, str):
        return [unique_fields]
    return list(unique_fields)


def _schema_field_names(schema: Type[BaseModel]) -> set:
    """Return set of field names for the schema (Pydantic v1 or v2)."""
    if hasattr(schema, "model_fields"):
        return set(schema.model_fields.keys())
    return set(getattr(schema, "__fields__", {}).keys())


def _model_column_names(model: type) -> set:
    """Return set of column/attribute names that can be set on the model (persisted columns only)."""
    return {c.key for c in sa_inspect(model).mapper.column_attrs}


def _make_hashable(obj: Any) -> Any:
    """Convert object to a hashable form for use in set/tuple (e.g. row signature)."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, list):
        return tuple(_make_hashable(x) for x in obj)
    if isinstance(obj, dict):
        return tuple(sorted((k, _make_hashable(v)) for k, v in obj.items()))
    try:
        hash(obj)
        return obj
    except TypeError:
        return str(obj)

async def import_excel_generic(
    file: UploadFile,
    session: AsyncSession,
    model: type,
    schema: Type[BaseModel],
    unique_fields: Union[str, List[str]],
    dry_run: bool = False,
    column_mapping: Optional[Dict[str, str]] = None,
    integrity_error_messages: Optional[Dict[str, str]] = None,
    inject_fields: Optional[Dict[str, Any]] = None,
    *,
    audit_account_id: Optional[int] = None,
) -> Dict:

    fn = (file.filename or "").lower()
    if not fn.endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(status_code=400, detail="Upload .xlsx, .xls, or .csv file only")

    fields = _normalize_unique_fields(unique_fields)
    if not fields:
        raise HTTPException(status_code=400, detail="At least one unique field is required")

    schema_fields = _schema_field_names(schema)
    model_columns = _model_column_names(model)
    column_mapping = {k.strip().lower(): v.strip().lower()
                      for k, v in (column_mapping or {}).items()}

    contents = await file.read()

    try:
        df = (
            pd.read_csv(BytesIO(contents))
            if fn.endswith(".csv")
            else pd.read_excel(BytesIO(contents))
        )

        df.columns = df.columns.str.strip().str.lower()
        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
        df = df.where(pd.notnull(df), None)
        records = df.to_dict(orient="records")

        inject_fields = inject_fields or {}

        def _row_for_schema(row: Dict) -> Dict:
            merged = {**row, **inject_fields}
            out = {k: merged[k] for k in schema_fields if k in merged}

            # Aircraft-specific created_at default
            if model.__name__ == "Aircraft" and "created_at" in schema_fields:
                if not out.get("created_at"):
                    out["created_at"] = datetime.now(timezone.utc)

            return out

        def _stmt_lookup(validated):
            stmt = select(model)
            for f in fields:
                stmt = stmt.where(getattr(model, f) == getattr(validated, f))
            return stmt

        async def _unique_field_taken(validated, exclude_id=None):
            stmt = select(model)
            for f in fields:
                stmt = stmt.where(getattr(model, f) == getattr(validated, f, None))
            if exclude_id and hasattr(model, "id"):
                stmt = stmt.where(model.id != exclude_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

        inserted = 0
        updated = 0
        errors: List[Dict] = []
        seen_row_signatures: set = set()
        aircraft_registrations: List[str] = []

        def _row_signature(validated):
            d = validated.dict()
            return tuple(sorted((k, _make_hashable(v)) for k, v in d.items()))

        # ---------- PASS 1: validation only ----------
        for idx, row in enumerate(records):
            try:
                validated = schema(**_row_for_schema(row))
                result = await session.execute(_stmt_lookup(validated))
                existing = result.scalar_one_or_none()
                updated += 1 if existing else 0
                inserted += 0 if existing else 1
            except Exception as e:
                errors.append({"row": idx + 2, "error": str(e)})

        if dry_run:
            return {"status": "dry-run", "inserted": inserted, "updated": updated, "errors": errors}

        if errors:
            await session.rollback()
            return {"status": "failed", "inserted": inserted, "updated": updated, "errors": errors}

        # ---------- PASS 2: write ----------
        with session.no_autoflush:
            for idx, row in enumerate(records):
                validated = schema(**_row_for_schema(row))
                sig = _row_signature(validated)

                if sig in seen_row_signatures:
                    continue

                result = await session.execute(_stmt_lookup(validated))
                existing = result.scalar_one_or_none()

                if existing:
                    conflict = await _unique_field_taken(validated, exclude_id=getattr(existing, "id", None))
                    if conflict:
                        errors.append({"row": idx + 2, "error": "Duplicate unique field value"})
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

                    if model.__name__ == "Aircraft":
                        aircraft_registrations.append(existing.registration)


                else:
                    conflict = await _unique_field_taken(validated)
                    if conflict:
                        errors.append({"row": idx + 2, "error": "Duplicate unique field value"})
                        continue

                    data = validated.dict()
                    payload = {k: data[k] for k in model_columns if k in data}
                    obj = model(**payload)
                    session.add(obj)
                    if audit_account_id is not None:
                        await set_audit_fields(obj, audit_account_id, is_create=True)

                    if model.__name__ == "Aircraft":
                        aircraft_registrations.append(obj.registration)

                seen_row_signatures.add(sig)

        if errors:
            await session.rollback()
            return {"status": "failed", "inserted": inserted, "updated": updated, "errors": errors}

        await session.commit()
        # ---------- POST-COMMIT HOOK (Aircraft only) ----------
        if model.__name__ == "Aircraft" and aircraft_registrations:
            result = await session.execute(
                select(Aircraft).where(Aircraft.registration.in_(aircraft_registrations))
            )
            aircraft_list = result.scalars().all()

            for aircraft in aircraft_list:
                fd_stmt = select(FleetDailyUpdate).where(
                    FleetDailyUpdate.aircraft_fk == aircraft.id
                )
                fd_result = await session.execute(fd_stmt)
                fd_row = fd_result.scalar_one_or_none()

                if fd_row:
                    fd_row.is_deleted = False
                    fd_row.status = FleetDailyUpdateStatusEnum.RUNNING.value
                    if audit_account_id is not None:
                        await set_audit_fields(
                            fd_row, audit_account_id, is_create=False
                        )
                else:
                    fd_new = FleetDailyUpdate(
                        aircraft_fk=aircraft.id,
                        status=FleetDailyUpdateStatusEnum.RUNNING.value,
                    )
                    session.add(fd_new)
                    if audit_account_id is not None:
                        await set_audit_fields(
                            fd_new, audit_account_id, is_create=True
                        )

            await session.commit()

        return {"status": "success", "inserted": inserted, "updated": updated}

    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Database integrity error")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")