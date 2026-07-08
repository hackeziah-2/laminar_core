"""ATL Excel import: validate all rows before any database write."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from pydantic import ValidationError

from app.constants.atl_excel_import import ATL_EXCEL_COLUMN_MAPPING
from app.schemas.aircraft_technical_log_schema import AircraftTechnicalLogImportSchema
from app.services.atl_import_references import AtlImportReferences
from app.services.excel_import.hooks.atl import AtlImportHook
from app.services.excel_import.row_builder import build_row_for_schema, schema_field_names
from app.services.excel_import.validation_errors import (
    build_field_labels,
    expected_hint_for_field,
    merge_structured_errors,
    structured_error_dict,
)

SCHEMA = AircraftTechnicalLogImportSchema
_HOOK = AtlImportHook()
_SCHEMA_FIELDS = schema_field_names(SCHEMA)
_FIELD_LABELS = build_field_labels(ATL_EXCEL_COLUMN_MAPPING)

_ACCOUNT_FK_FIELDS: Dict[str, str] = {
    "remark_person": "Remark Person",
    "actiontaken_person": "Action Taken Person",
    "pilot_fk": "Pilot",
    "maintenance_fk": "Maintenance",
    "pilot_accepted_by": "Pilot Accepted By",
    "rts_signed_by": "RTS Signed By",
}


def _trim_row_strings(row: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, str):
            out[key] = value.strip()
        else:
            out[key] = value
    return out


def validate_atl_row_schema(
    row: Dict[str, Any],
    *,
    excel_row: int,
    inject_fields: Dict[str, Any],
) -> Tuple[Optional[AircraftTechnicalLogImportSchema], List[Dict[str, Any]]]:
    """Validate one ATL row; return (validated_model, structured_errors)."""
    from app.services.excel_import.validation_errors import (
        exception_to_structured_errors,
        pydantic_errors_to_structured,
    )

    trimmed = _trim_row_strings(row)
    try:
        row_data = build_row_for_schema(
            trimmed,
            schema_fields=_SCHEMA_FIELDS,
            inject_fields=inject_fields,
            hook=_HOOK,
        )
        validated = SCHEMA(**row_data)
        return validated, []
    except ValidationError as exc:
        return None, pydantic_errors_to_structured(
            exc,
            excel_row=excel_row,
            raw_row=trimmed,
            field_labels=_FIELD_LABELS,
        )
    except Exception as exc:
        return None, exception_to_structured_errors(
            exc,
            excel_row=excel_row,
            raw_row=trimmed,
            field_labels=_FIELD_LABELS,
        )


def _duplicate_row_errors(
    records: Sequence[Dict[str, Any]],
    *,
    inject_fields: Dict[str, Any],
) -> List[Dict[str, Any]]:
    seen: Dict[Tuple[Any, ...], int] = {}
    errors: List[Dict[str, Any]] = []
    for idx, row in enumerate(records):
        excel_row = idx + 2
        seq = row.get("sequence_no")
        if seq is None or (isinstance(seq, str) and not str(seq).strip()):
            continue
        key = (
            inject_fields.get("aircraft_fk"),
            str(seq).strip(),
            inject_fields.get("atl_batch_fk"),
        )
        if key in seen:
            first_row = seen[key]
            errors.append(
                structured_error_dict(
                    row=excel_row,
                    column=_FIELD_LABELS.get("sequence_no", "Sequence No"),
                    value=seq,
                    error=f"Duplicate sequence number (also appears on row {first_row}).",
                    expected="Each sequence number must appear only once per import.",
                )
            )
        else:
            seen[key] = excel_row
    return errors


def validate_account_reference_fields(
    validated_rows: Sequence[Tuple[int, AircraftTechnicalLogImportSchema]],
    references: AtlImportReferences,
) -> List[Dict[str, Any]]:
    """Validate account FK fields using preloaded reference cache (no DB queries)."""
    errors: List[Dict[str, Any]] = []
    valid_ids = references.valid_account_ids
    for excel_row, validated in validated_rows:
        for field, label in _ACCOUNT_FK_FIELDS.items():
            value = getattr(validated, field, None)
            if value is None:
                continue
            if int(value) not in valid_ids:
                errors.append(
                    structured_error_dict(
                        row=excel_row,
                        column=label,
                        value=value,
                        error="Reference not found.",
                        expected=expected_hint_for_field(field),
                    )
                )
    return errors


def validate_atl_schema_and_duplicates(
    records: Sequence[Dict[str, Any]],
    *,
    inject_fields: Dict[str, Any],
) -> Tuple[List[Tuple[int, AircraftTechnicalLogImportSchema]], List[Dict[str, Any]]]:
    """CPU-only validation: schema + in-file duplicates (no database access)."""
    schema_errors: List[Dict[str, Any]] = []
    validated_rows: List[Tuple[int, AircraftTechnicalLogImportSchema]] = []

    for idx, row in enumerate(records):
        excel_row = idx + 2
        validated, row_errors = validate_atl_row_schema(
            row,
            excel_row=excel_row,
            inject_fields=inject_fields,
        )
        if row_errors:
            schema_errors.extend(row_errors)
        elif validated is not None:
            validated_rows.append((excel_row, validated))

    duplicate_errors = _duplicate_row_errors(records, inject_fields=inject_fields)
    all_errors = merge_structured_errors(schema_errors, duplicate_errors)
    if all_errors:
        return [], all_errors
    return validated_rows, []


async def validate_atl_import_records(
    session,
    records: Sequence[Dict[str, Any]],
    *,
    inject_fields: Dict[str, Any],
) -> Tuple[List[Tuple[int, AircraftTechnicalLogImportSchema]], List[Dict[str, Any]]]:
    """
    Validate every ATL row and collect all errors.

    Loads reference data once for account FK checks when schema validation passes.
    """
    from app.services.atl_import_references import (
        collect_account_ids_from_validated_rows,
        load_atl_import_references,
    )

    validated_rows, errors = validate_atl_schema_and_duplicates(
        records,
        inject_fields=inject_fields,
    )
    if errors:
        return [], errors

    aircraft_fk = int(inject_fields["aircraft_fk"])
    atl_batch_fk = int(inject_fields["atl_batch_fk"])
    account_ids = collect_account_ids_from_validated_rows(validated_rows)
    references = await load_atl_import_references(
        session,
        aircraft_fk=aircraft_fk,
        atl_batch_fk=atl_batch_fk,
        account_ids=account_ids,
    )
    reference_errors = validate_account_reference_fields(validated_rows, references)
    if reference_errors:
        return [], reference_errors
    return validated_rows, []


def preprocess_atl_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return _HOOK.preprocess_records(records)
