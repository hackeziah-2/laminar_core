"""Read uploaded Excel/CSV into row dicts."""
from __future__ import annotations

import csv
from io import BytesIO, StringIO
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import UploadFile

from app.core.exceptions import ValidationError as AppValidationError
from app.services.excel_import.parsers import sanitize_spreadsheet_value


ALLOWED_EXTENSIONS = (".xlsx", ".xls", ".csv")


def normalize_column_mapping(
    column_mapping: Optional[Dict[str, str]],
) -> Dict[str, str]:
    if not column_mapping:
        return {}
    return {k.strip().lower(): v.strip().lower() for k, v in column_mapping.items()}


def _detect_csv_delimiter(contents: bytes) -> str:
    """Detect comma vs tab (and other common delimiters) for spreadsheet exports."""
    sample = contents[:8192].decode("utf-8-sig", errors="replace")
    if not sample.strip():
        return ","
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        return dialect.delimiter
    except csv.Error:
        header_line = sample.splitlines()[0] if sample.splitlines() else sample
        if "\t" in header_line and header_line.count("\t") >= header_line.count(","):
            return "\t"
        return ","


def _read_csv_dataframe(contents: bytes) -> pd.DataFrame:
    delimiter = _detect_csv_delimiter(contents)
    df = pd.read_csv(BytesIO(contents), sep=delimiter)
    if len(df.columns) == 1 and delimiter != "\t":
        first_col = str(df.columns[0])
        if "\t" in first_col:
            df = pd.read_csv(StringIO(contents.decode("utf-8-sig", errors="replace")), sep="\t")
    return df


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
            df = _read_csv_dataframe(contents)
        else:
            df = pd.read_excel(BytesIO(contents))
    except Exception as exc:
        raise AppValidationError(f"Could not parse spreadsheet: {exc}") from exc

    df.columns = (
        df.columns.str.strip().str.lower().str.replace(r"\s+", " ", regex=True)
    )
    mapping = normalize_column_mapping(column_mapping)
    df = df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})
    df = df.where(pd.notnull(df), None)
    return [
        {k: sanitize_spreadsheet_value(v) for k, v in row.items()}
        for row in df.to_dict(orient="records")
    ]
