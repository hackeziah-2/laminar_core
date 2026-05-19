"""Read uploaded Excel/CSV into row dicts."""
from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import UploadFile

from app.core.exceptions import ValidationError as AppValidationError


ALLOWED_EXTENSIONS = (".xlsx", ".xls", ".csv")


def normalize_column_mapping(
    column_mapping: Optional[Dict[str, str]],
) -> Dict[str, str]:
    if not column_mapping:
        return {}
    return {k.strip().lower(): v.strip().lower() for k, v in column_mapping.items()}


async def read_upload_records(
    file: UploadFile,
    *,
    column_mapping: Optional[Dict[str, str]] = None,
    allowed_extensions: tuple = ALLOWED_EXTENSIONS,
) -> List[Dict[str, Any]]:
    fn = (file.filename or "").lower()
    if not fn.endswith(allowed_extensions):
        raise AppValidationError(
            f"Upload {', '.join(allowed_extensions)} file only"
        )

    contents = await file.read()
    if not contents:
        raise AppValidationError("Uploaded file is empty")

    try:
        if fn.endswith(".csv"):
            df = pd.read_csv(BytesIO(contents))
        else:
            df = pd.read_excel(BytesIO(contents))
    except Exception as exc:
        raise AppValidationError(f"Could not parse spreadsheet: {exc}") from exc

    df.columns = df.columns.str.strip().str.lower()
    mapping = normalize_column_mapping(column_mapping)
    df = df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})
    df = df.where(pd.notnull(df), None)
    return df.to_dict(orient="records")
