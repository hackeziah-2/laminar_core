"""Read uploaded Excel/CSV into row dicts."""
from __future__ import annotations

import csv
import os
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
import pandas as pd
from fastapi import UploadFile

from app.core.exceptions import ValidationError as AppValidationError
from app.services.excel_import.parsers import sanitize_spreadsheet_value
from app.services.file_upload_service import CHUNK_SIZE, max_upload_bytes


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


def _read_csv_dataframe_from_path(
    path: Path, *, preserve_numeric_text: bool = False
) -> pd.DataFrame:
    sample = path.read_bytes()[:8192]
    delimiter = _detect_csv_delimiter(sample)
    read_kwargs: Dict[str, Any] = {"sep": delimiter}
    if preserve_numeric_text:
        read_kwargs["dtype"] = str
    df = pd.read_csv(path, **read_kwargs)
    if len(df.columns) == 1 and delimiter != "\t":
        first_col = str(df.columns[0])
        if "\t" in first_col:
            df = pd.read_csv(
                path,
                sep="\t",
                dtype=str if preserve_numeric_text else None,
            )
    return df


async def _stream_upload_to_temp_path(file: UploadFile, suffix: str) -> Path:
    """Write the upload in chunks to a temp file; delete the file on failure."""
    max_bytes = max_upload_bytes()
    fd, raw_path = tempfile.mkstemp(suffix=suffix or ".bin")
    os.close(fd)
    dest = Path(raw_path)
    total = 0
    try:
        async with aiofiles.open(dest, "wb") as output:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise AppValidationError(
                        f"File exceeds the {max_bytes} byte limit."
                    )
                await output.write(chunk)
        if total == 0:
            raise AppValidationError("Uploaded file is empty")
        return dest
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    finally:
        close = getattr(file, "close", None)
        if close is not None:
            try:
                result = close()
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                pass


def _records_from_dataframe(
    df: pd.DataFrame,
    column_mapping: Optional[Dict[str, str]],
) -> List[Dict[str, Any]]:
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


async def read_upload_records(
    file: UploadFile,
    *,
    column_mapping: Optional[Dict[str, str]] = None,
    allowed_extensions: tuple = ALLOWED_EXTENSIONS,
    preserve_numeric_text: bool = False,
) -> List[Dict[str, Any]]:
    fn = (file.filename or "").lower()
    if not fn.endswith(allowed_extensions):
        raise AppValidationError(
            f"Upload {', '.join(allowed_extensions)} file only"
        )

    suffix = Path(fn).suffix or ".bin"
    dest = await _stream_upload_to_temp_path(file, suffix)
    try:
        try:
            if fn.endswith(".csv"):
                df = _read_csv_dataframe_from_path(
                    dest, preserve_numeric_text=preserve_numeric_text
                )
            else:
                df = pd.read_excel(
                    dest,
                    dtype=str if preserve_numeric_text else None,
                )
        except AppValidationError:
            raise
        except Exception as exc:
            raise AppValidationError(f"Could not parse spreadsheet: {exc}") from exc
        return _records_from_dataframe(df, column_mapping)
    finally:
        dest.unlink(missing_ok=True)


def read_atl_spreadsheet_bytes(
    contents: bytes,
    *,
    column_mapping: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Read ATL Excel bytes preserving numeric cell text for exact decimal import."""
    df = pd.read_excel(BytesIO(contents), dtype=str)
    return _records_from_dataframe(df, column_mapping)
