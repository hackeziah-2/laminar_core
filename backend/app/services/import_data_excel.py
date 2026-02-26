"""
Generic Excel/CSV import for any SQLAlchemy model.

Use import_excel_generic() with your model, Pydantic schema, and unique field(s).
Optional: column_mapping (Excel header -> schema field), integrity_error_messages (constraint -> user message),
inject_fields (merge into each row before validation, e.g. aircraft_fk from endpoint).
"""
from typing import Any, Dict, List, Optional, Type, Union

import pandas as pd
from fastapi import HTTPException, UploadFile
from io import BytesIO
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect as sa_inspect

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
) -> Dict:
    """
    Import rows from Excel (.xlsx, .xls) or CSV into any SQLAlchemy model.

    - model: SQLAlchemy model class (e.g. Aircraft, SomeOtherModel).
    - schema: Pydantic model for validation; only schema fields are read from the file.
    - unique_fields: column name(s) used to detect existing rows (update vs insert).
    - column_mapping: optional dict mapping Excel header (lowercase) -> schema field name.
    - integrity_error_messages: optional dict of substring -> user message for IntegrityError.
    - inject_fields: optional dict merged into each row before validation (injected keys override file).
    """
    fn = (file.filename or "").lower()
    if not (fn.endswith(".xlsx") or fn.endswith(".xls") or fn.endswith(".csv")):
        raise HTTPException(status_code=400, detail="Upload .xlsx, .xls, or .csv file only")

    fields = _normalize_unique_fields(unique_fields)
    if not fields:
        raise HTTPException(status_code=400, detail="At least one unique field is required")

    schema_fields = _schema_field_names(schema)
    model_columns = _model_column_names(model)
    column_mapping = column_mapping or {}
    # Normalize mapping keys to lowercase to match normalized Excel headers
    column_mapping = {k.strip().lower(): v.strip().lower() for k, v in column_mapping.items()}

    contents = await file.read()

    try:
        if fn.endswith(".csv"):
            df = pd.read_csv(BytesIO(contents))
        else:
            df = pd.read_excel(BytesIO(contents))
        df.columns = df.columns.str.strip().str.lower()
        # Apply column mapping: rename columns for schema compatibility
        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
        df = df.where(pd.notnull(df), None)
        records = df.to_dict(orient="records")

        inject_fields = inject_fields or {}

        def _row_for_schema(row: Dict) -> Dict:
            """Merge inject_fields into row, then keep only keys that exist in the schema."""
            merged = {**row, **inject_fields}
            return {k: merged[k] for k in schema_fields if k in merged}

        inserted = 0
        updated = 0
        errors: List[Dict] = []

        def _stmt_lookup(validated, include_deleted: bool = True):
            """Find existing row where ALL unique fields match. Includes soft-deleted rows so import can restore them."""
            stmt = select(model)
            for f in fields:
                stmt = stmt.where(getattr(model, f) == getattr(validated, f))
            if hasattr(model, "is_deleted") and not include_deleted:
                stmt = stmt.where(model.is_deleted == False)
            return stmt

        async def _unique_field_taken(validated, exclude_id=None) -> Optional[str]:
            """Check if another row has the same combination of ALL unique fields (composite key).
            Returns first field name if conflict, else None. Used to avoid duplicate key on insert/update."""
            stmt = select(model)
            for f in fields:
                stmt = stmt.where(getattr(model, f) == getattr(validated, f, None))
            if exclude_id is not None and hasattr(model, "id"):
                stmt = stmt.where(model.id != exclude_id)
            result = await session.execute(stmt)
            if result.scalar_one_or_none():
                return fields[0]
            return None

        # First pass: validate and count inserts/updates
        for idx, row in enumerate(records):
            try:
                validated = schema(**_row_for_schema(row))

                # Check existing by unique field (incl. soft-deleted to allow restore)
                result = await session.execute(_stmt_lookup(validated))
                existing = result.scalar_one_or_none()

                if existing:
                    updated += 1
                else:
                    inserted += 1

            except Exception as e:
                errors.append({"row": idx + 2, "error": str(e)})

        # Dry-run returns only validation + counts
        if dry_run:
            return {"status": "dry-run", "inserted": inserted, "updated": updated, "errors": errors}

        if errors:
            await session.rollback()
            return {"status": "failed", "inserted": inserted, "updated": updated, "errors": errors}

        # Second pass: insert or update (no_autoflush avoids premature flush on select)
        with session.no_autoflush:
            for idx, row in enumerate(records):
                validated = schema(**_row_for_schema(row))
                result = await session.execute(_stmt_lookup(validated))
                existing = result.scalar_one_or_none()

                if existing:
                    # Check unique fields not taken by other rows before update
                    conflict = await _unique_field_taken(validated, exclude_id=getattr(existing, "id", None))
                    if conflict:
                        val = getattr(validated, conflict, "")
                        errors.append({"row": idx + 2, "error": f"{conflict} '{val}' already exists"})
                        continue
                    data = validated.dict()
                    for key in model_columns:
                        if key in data:
                            setattr(existing, key, data[key])
                    # Restore if was soft-deleted
                    if hasattr(existing, "is_deleted") and existing.is_deleted:
                        existing.is_deleted = False
                else:
                    # Before insert: check any unique field already taken
                    conflict = await _unique_field_taken(validated)
                    if conflict:
                        val = getattr(validated, conflict, "")
                        errors.append({"row": idx + 2, "error": f"{conflict} '{val}' already exists"})
                        continue
                    data = validated.dict()
                    payload = {k: data[k] for k in model_columns if k in data}
                    session.add(model(**payload))

        if errors:
            await session.rollback()
            return {"status": "failed", "inserted": inserted, "updated": updated, "errors": errors}

        try:
            await session.commit()
            return {"status": "success", "inserted": inserted, "updated": updated}
        except IntegrityError as e:
            await session.rollback()
            msg = str(e.orig) if hasattr(e, "orig") and e.orig else str(e)
            msg_lower = msg.lower()
            if integrity_error_messages:
                for pattern, detail in integrity_error_messages.items():
                    if pattern.lower() in msg_lower:
                        raise HTTPException(status_code=400, detail=detail)
            # Suggest running migrations when enum value is invalid
            if "invalid input value for enum" in msg_lower or "invalidtextrepresentation" in msg_lower:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid enum value (e.g. nature_of_flight). Run migrations: docker compose exec backend alembic upgrade head",
                )
            raise HTTPException(status_code=400, detail="Duplicate value: a record with this data already exists")

    except HTTPException:
        raise
    except IntegrityError:
        raise
    except Exception as e:
        msg = str(e).lower()
        if "invalid input value for enum" in msg or "invalidtextrepresentation" in msg:
            raise HTTPException(
                status_code=400,
                detail="Invalid enum value (e.g. nature_of_flight ATL_REPL). Run migrations: docker compose exec backend alembic upgrade head",
            )
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")
