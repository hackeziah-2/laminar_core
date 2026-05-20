from __future__ import annotations

from datetime import date
from typing import Any, Optional, Set

from pydantic import BaseModel

from app.repository.import_prerequisites import resolve_atl_id_by_sequence_no
from app.services.cpcp_computation import apply_cpcp_next_due_fields
from app.services.excel_import.hooks.base import ImportHook
from app.services.excel_import.parsers import coerce_import_float, is_spreadsheet_empty, parse_import_date

_CPCP_DATE_FIELDS = ("last_done_date", "next_due_date")
_CPCP_FLOAT_FIELDS = (
    "interval_hours",
    "interval_months",
    "last_done_tach",
    "last_done_aftt",
    "next_due_tach",
    "next_due_aftt",
)


def _sanitize_cpcp_obj_for_db(obj: Any) -> None:
    """Ensure no pandas NaT/NaN reaches asyncpg on flush."""
    for name in _CPCP_DATE_FIELDS:
        val = getattr(obj, name, None)
        if is_spreadsheet_empty(val):
            setattr(obj, name, None)
            continue
        if not isinstance(val, date):
            parsed = parse_import_date(val)
            setattr(
                obj,
                name,
                parsed if isinstance(parsed, date) else None,
            )
    for name in _CPCP_FLOAT_FIELDS:
        setattr(obj, name, coerce_import_float(getattr(obj, name, None)))


class MaintenanceCpcpImportHook(ImportHook):
    def apply_defaults(self, out: dict[str, Any], schema_fields: Set[str]) -> None:
        if "description" in schema_fields and out.get("description") is None:
            out["description"] = None

    async def after_upsert(
        self,
        session,
        *,
        validated: BaseModel,
        existing,
        obj: Any,
        audit_account_id: Optional[int],
    ) -> None:
        aircraft_id = getattr(obj, "aircraft_id", None) or getattr(validated, "aircraft_id", None)
        if aircraft_id is None:
            return

        _sanitize_cpcp_obj_for_db(obj)

        atl_sequence = getattr(validated, "atl_sequence", None)
        if atl_sequence is not None and str(atl_sequence).strip():
            obj.atl_ref = await resolve_atl_id_by_sequence_no(
                session,
                aircraft_fk=aircraft_id,
                sequence_no=atl_sequence,
            )
        else:
            obj.atl_ref = None

        apply_cpcp_next_due_fields(obj)
        _sanitize_cpcp_obj_for_db(obj)
