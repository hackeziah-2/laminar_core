"""Structured spreadsheet import validation errors."""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from pydantic import ValidationError

from app.services.excel_import.parsers import is_spreadsheet_empty

_FIELD_EXPECTED_HINTS: Dict[str, str] = {
    "sequence_no": "Non-empty text or number (e.g. 001).",
    "origin_date": "DD/MM/YYYY, MM/DD/YYYY, DD-Mon-YY, or YYYY-MM-DD.",
    "destination_date": "DD/MM/YYYY, MM/DD/YYYY, DD-Mon-YY, or YYYY-MM-DD.",
    "pilot_accept_date": "DD/MM/YYYY, MM/DD/YYYY, DD-Mon-YY, or YYYY-MM-DD.",
    "rts_date": "DD/MM/YYYY, MM/DD/YYYY, DD-Mon-YY, or YYYY-MM-DD.",
    "origin_time": "HH:MM, HHMM, or Zulu time (e.g. 0440 Zulu).",
    "destination_time": "HH:MM, HHMM, or Zulu time (e.g. 0440 Zulu).",
    "pilot_accept_time": "HH:MM, HHMM, or Zulu time (e.g. 0440 Zulu).",
    "rts_time": "HH:MM, HHMM, or Zulu time (e.g. 0440 Zulu).",
    "date_time_reported": "DD-Mon-YY HHMMZ (e.g. 01-Mar-24 0738Z) or ISO datetime.",
    "date_time_released": "DD-Mon-YY HHMMZ (e.g. 01-Mar-24 0738Z) or ISO datetime.",
    "nature_of_flight": "TR, PSF, PRF, EGR, ME, TR_WITH_PIREM, VOID, ATL_REPL, CANCELLED_FLT, "
    "BLANK, MISSING, or NO ENTRY.",
    "work_status": "FOR_REVIEW, AWAITING_ATTACHMENT, REJECTED_MAINTENANCE, APPROVED, "
    "REJECTED_QUALITY, PENDING, or COMPLETED.",
    "number_of_landings": "Whole number.",
    "remark_person": "Valid account ID.",
    "actiontaken_person": "Valid account ID.",
    "pilot_fk": "Valid account ID.",
    "maintenance_fk": "Valid account ID.",
    "pilot_accepted_by": "Valid account ID.",
    "rts_signed_by": "Valid account ID.",
}

_NUMERIC_FIELDS = frozenset(
    {
        "tach_time_due",
        "hobbs_meter_start",
        "hobbs_meter_end",
        "hobbs_meter_total",
        "tachometer_start",
        "tachometer_end",
        "tachometer_total",
        "airframe_prev_time",
        "airframe_flight_time",
        "airframe_total_time",
        "airframe_run_time",
        "airframe_aftt",
        "engine_prev_time",
        "engine_flight_time",
        "engine_total_time",
        "engine_run_time",
        "engine_tso",
        "engine_tbo",
        "propeller_prev_time",
        "propeller_flight_time",
        "propeller_total_time",
        "propeller_run_time",
        "propeller_tsn",
        "propeller_tso",
        "propeller_tbo",
        "life_time_limit_engine",
        "life_time_limit_propeller",
        "fuel_qty_left_uplift_qty",
        "fuel_qty_right_uplift_qty",
        "fuel_qty_left_prior_departure",
        "fuel_qty_right_prior_departure",
        "fuel_qty_left_after_on_blks",
        "fuel_qty_right_after_on_blks",
        "oil_qty_uplift_qty",
        "oil_qty_prior_departure",
        "oil_qty_after_on_blks",
    }
)

_INTEGER_FIELDS = frozenset(
    {
        "number_of_landings",
        "remark_person",
        "actiontaken_person",
        "pilot_fk",
        "maintenance_fk",
        "pilot_accepted_by",
        "rts_signed_by",
    }
)


def humanize_field_name(field: str) -> str:
    return field.replace("_", " ").strip().title()


def build_field_labels(column_mapping: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    """Map schema field names to spreadsheet-friendly column labels."""
    labels: Dict[str, str] = {}
    if column_mapping:
        for header, field in column_mapping.items():
            if field in labels:
                continue
            cleaned = header.strip()
            if cleaned.isupper() and len(cleaned) > 3:
                cleaned = cleaned.title()
            labels[field] = cleaned
    return labels


def format_display_value(value: Any) -> str:
    if is_spreadsheet_empty(value):
        return "(blank)"
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value).strip()


def expected_hint_for_field(field: str) -> Optional[str]:
    if field in _FIELD_EXPECTED_HINTS:
        return _FIELD_EXPECTED_HINTS[field]
    if field in _INTEGER_FIELDS:
        return "Whole number."
    if field in _NUMERIC_FIELDS:
        return "Numeric value."
    return None


def _loc_to_field(loc: Sequence[Union[str, int]]) -> str:
    parts: List[str] = []
    for item in loc:
        if isinstance(item, int):
            parts.append(f"[{item}]")
        else:
            parts.append(str(item))
    return ".".join(parts) if parts else "row"


def _message_for_pydantic_error(err: Dict[str, Any], field: str) -> str:
    msg = str(err.get("msg") or "Invalid value.")
    err_type = err.get("type")
    if err_type == "value_error.missing" or "field required" in msg.lower():
        return "This field is required."
    if err_type == "type_error.integer" or "valid integer" in msg.lower():
        return "Must be a numeric value."
    if err_type == "type_error.float" or "valid number" in msg.lower():
        return "Must be a numeric value."
    if err_type == "type_error.bool":
        return "Must be true or false."
    if "invalid date" in msg.lower() or err_type == "value_error.date":
        return "Invalid date."
    if err_type == "enum" or "value is not a valid enumeration" in msg.lower():
        return "Invalid value."
    if field in _INTEGER_FIELDS and "numeric" in msg.lower():
        return "Must be a numeric value."
    return msg.rstrip(".")


def _value_from_raw_row(raw_row: Optional[Dict[str, Any]], field: str) -> Any:
    if not raw_row or not field:
        return None
    if field in raw_row:
        return raw_row[field]
    top_level = field.split(".")[0].split("[")[0]
    if top_level in raw_row:
        return raw_row[top_level]
    return None


def structured_error_dict(
    *,
    row: int,
    column: str,
    value: Any,
    error: str,
    expected: Optional[str] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "row": row,
        "column": column,
        "value": format_display_value(value),
        "error": error,
    }
    if expected:
        out["expected"] = expected
    legacy = f"{column}: {error}"
    if expected:
        legacy = f"{legacy}. Expected: {expected}"
    out["error_legacy"] = legacy
    return out


def pydantic_errors_to_structured(
    exc: ValidationError,
    *,
    excel_row: int,
    raw_row: Optional[Dict[str, Any]] = None,
    field_labels: Optional[Mapping[str, str]] = None,
) -> List[Dict[str, Any]]:
    labels = dict(field_labels or {})
    structured: List[Dict[str, Any]] = []
    for err in exc.errors():
        loc = err.get("loc") or ()
        field = _loc_to_field(loc)
        top_field = str(loc[0]) if loc else field
        column = labels.get(top_field, humanize_field_name(top_field))
        value = _value_from_raw_row(raw_row, top_field)
        message = _message_for_pydantic_error(err, top_field)
        expected = expected_hint_for_field(top_field)
        if expected and message == "Invalid value.":
            message = "Invalid value."
        structured.append(
            structured_error_dict(
                row=excel_row,
                column=column,
                value=value,
                error=message,
                expected=expected,
            )
        )
    return structured


def exception_to_structured_errors(
    exc: Exception,
    *,
    excel_row: int,
    raw_row: Optional[Dict[str, Any]] = None,
    field_labels: Optional[Mapping[str, str]] = None,
    default_column: str = "Row",
) -> List[Dict[str, Any]]:
    if isinstance(exc, ValidationError):
        return pydantic_errors_to_structured(
            exc,
            excel_row=excel_row,
            raw_row=raw_row,
            field_labels=field_labels,
        )
    return [
        structured_error_dict(
            row=excel_row,
            column=default_column,
            value=None,
            error=str(exc).strip() or "Invalid row.",
        )
    ]


def format_row_error(exc: Exception) -> str:
    """Backward-compatible single-string row error."""
    if isinstance(exc, ValidationError):
        parts = []
        for err in exc.errors():
            loc = ".".join(str(x) for x in err.get("loc", ()))
            parts.append(f"{loc}: {err.get('msg')}")
        return "; ".join(parts) if parts else str(exc)
    return str(exc)


def format_error_report_markdown(errors: Sequence[Mapping[str, Any]]) -> str:
    if not errors:
        return ""
    lines = [
        "Import Failed",
        "",
        "The file contains validation errors. No records were imported.",
        "",
        "| Row | Column | Value | Error |",
        "|-----|--------|-------|-------|",
    ]
    for item in errors:
        row = item.get("row", "")
        column = item.get("column", "")
        value = item.get("value", "")
        error = item.get("error", "")
        expected = item.get("expected")
        if expected:
            error = f"{error} Expected: {expected}."
        lines.append(f"| {row} | {column} | {value} | {error} |")
    return "\n".join(lines)


def format_error_report_csv(errors: Sequence[Mapping[str, Any]]) -> str:
    import csv
    from io import StringIO

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["row", "column", "value", "error", "expected"])
    for item in errors:
        writer.writerow(
            [
                item.get("row", ""),
                item.get("column", ""),
                item.get("value", ""),
                item.get("error", ""),
                item.get("expected", ""),
            ]
        )
    return buffer.getvalue()


def merge_structured_errors(*groups: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    for group in groups:
        merged.extend(group)
    merged.sort(key=lambda e: (int(e.get("row", 0)), str(e.get("column", ""))))
    return merged
