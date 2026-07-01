"""Build validated row payloads from raw spreadsheet dicts."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Set, Type

from pydantic import BaseModel, ValidationError

from app.services.excel_import.hooks.base import ImportHook
from app.services.excel_import.parsers import (
    normalize_import_nature_of_flight,
    parse_import_date,
)
from app.services.excel_import.validation_errors import format_row_error

_IMPORT_DATE_FIELDS = frozenset(
    {
        "origin_date",
        "destination_date",
        "pilot_accept_date",
        "rts_date",
        "performed_date_start",
        "performed_date_end",
        "compli_date",
        "last_done_date",
    }
)


def schema_field_names(schema: Type[BaseModel]) -> Set[str]:
    if hasattr(schema, "model_fields"):
        return set(schema.model_fields.keys())
    return set(getattr(schema, "__fields__", {}).keys())


def build_row_for_schema(
    row: Dict[str, Any],
    *,
    schema_fields: Set[str],
    inject_fields: Dict[str, Any],
    hook: ImportHook,
) -> Dict[str, Any]:
    merged = {**row, **inject_fields}
    hook.transform_row(merged)
    out: Dict[str, Any] = {}
    for key in schema_fields:
        if key not in merged:
            continue
        val = merged[key]
        if key in _IMPORT_DATE_FIELDS:
            val = parse_import_date(val)
        elif key == "nature_of_flight":
            val = normalize_import_nature_of_flight(val)
        out[key] = val
    hook.apply_defaults(out, schema_fields)
    return out
