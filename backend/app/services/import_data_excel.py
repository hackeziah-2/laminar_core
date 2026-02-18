from typing import Dict, List, Type, Union

import pandas as pd
from fastapi import HTTPException, UploadFile
from io import BytesIO
from pydantic import BaseModel
from sqlalchemy import select
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

    if not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Upload .xlsx file only")

    fields = _normalize_unique_fields(unique_fields)
    if not fields:
        raise HTTPException(status_code=400, detail="At least one unique field is required")

    contents = await file.read()

    try:
        df = pd.read_excel(BytesIO(contents))
        df.columns = df.columns.str.strip().str.lower()
        df = df.where(pd.notnull(df), None)
        records = df.to_dict(orient="records")

        inserted = 0
        updated = 0
        errors: List[Dict] = []

        def _stmt_lookup(validated):
            stmt = select(model)
            for f in fields:
                stmt = stmt.where(getattr(model, f) == getattr(validated, f))
            if hasattr(model, "is_deleted"):
                stmt = stmt.where(model.is_deleted == False)
            return stmt

        # First pass: validate and count inserts/updates
        for idx, row in enumerate(records):
            try:
                validated = schema(**row)

                # Check existing by unique field (exclude soft-deleted)
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
        for row in records:
            validated = schema(**row)
            result = await session.execute(_stmt_lookup(validated))
            existing = result.scalar_one_or_none()

            if existing:
                for key, value in validated.dict().items():
                    setattr(existing, key, value)
            else:
                session.add(model(**validated.dict()))

        await session.commit()
        return {"status": "success", "inserted": inserted, "updated": updated}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")
