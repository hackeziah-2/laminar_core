from typing import Dict, List, Optional, Type, Union

import pandas as pd
from fastapi import HTTPException, UploadFile
from io import BytesIO
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

def _normalize_unique_fields(unique_fields: Union[str, List[str]]) -> List[str]:
    """Accept a single field name or a list of field names."""
    if isinstance(unique_fields, str):
        return [unique_fields]
    return list(unique_fields)


async def import_excel_generic(
    file: UploadFile,
    session: AsyncSession,
    model: type,            # SQLAlchemy model
    schema: Type[BaseModel],# Pydantic schema
    unique_fields: Union[str, List[str]],  # Column(s) used to check duplicates
    dry_run: bool = False,
) -> Dict:

    fn = (file.filename or "").lower()
    if not (fn.endswith(".xlsx") or fn.endswith(".xls") or fn.endswith(".csv")):
        raise HTTPException(status_code=400, detail="Upload .xlsx, .xls, or .csv file only")

    fields = _normalize_unique_fields(unique_fields)
    if not fields:
        raise HTTPException(status_code=400, detail="At least one unique field is required")

    contents = await file.read()

    try:
        if fn.endswith(".csv"):
            df = pd.read_csv(BytesIO(contents))
        else:
            df = pd.read_excel(BytesIO(contents))
        df.columns = df.columns.str.strip().str.lower()
        df = df.where(pd.notnull(df), None)
        records = df.to_dict(orient="records")

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
            """Check if any unique field value already exists in another row (incl. soft-deleted). Returns field name if conflict, else None."""
            for f in fields:
                val = getattr(validated, f, None)
                if val is None:
                    continue
                stmt = select(model).where(getattr(model, f) == val)
                # Include soft-deleted: unique constraint applies to all rows
                if exclude_id is not None and hasattr(model, "id"):
                    stmt = stmt.where(model.id != exclude_id)
                result = await session.execute(stmt)
                if result.scalar_one_or_none():
                    return f
            return None

        # First pass: validate and count inserts/updates
        for idx, row in enumerate(records):
            try:
                validated = schema(**row)

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

        # Second pass: insert or update
        for idx, row in enumerate(records):
            validated = schema(**row)
            result = await session.execute(_stmt_lookup(validated))
            existing = result.scalar_one_or_none()

            if existing:
                # Check unique fields not taken by other rows before update
                conflict = await _unique_field_taken(validated, exclude_id=getattr(existing, "id", None))
                if conflict:
                    val = getattr(validated, conflict, "")
                    errors.append({"row": idx + 2, "error": f"{conflict} '{val}' already exists"})
                    continue
                for key, value in validated.dict().items():
                    setattr(existing, key, value)
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
                session.add(model(**validated.dict()))

        if errors:
            await session.rollback()
            return {"status": "failed", "inserted": inserted, "updated": updated, "errors": errors}

        try:
            await session.commit()
            return {"status": "success", "inserted": inserted, "updated": updated}
        except IntegrityError as e:
            await session.rollback()
            # Parse constraint name for friendly message
            msg = str(e.orig) if hasattr(e, "orig") and e.orig else str(e)
            if "registration" in msg.lower() or "ix_aircrafts_registration" in msg:
                raise HTTPException(status_code=400, detail="Aircraft with this registration already exists")
            if "msn" in msg.lower() or "ix_aircrafts_msn" in msg:
                raise HTTPException(status_code=400, detail="Aircraft with this MSN already exists")
            raise HTTPException(status_code=400, detail="Duplicate value: a record with this data already exists")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")
