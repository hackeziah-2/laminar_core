from __future__ import annotations

from datetime import date
from typing import Any, Optional, Set

from pydantic import BaseModel

from app.models.tcc_maintenance import MethodOfComplianceEnum, TCCCategoryEnum
from app.repository.import_prerequisites import resolve_atl_id_by_sequence_no
from app.services.excel_import.hooks.base import ImportHook
from app.services.excel_import.parsers import coerce_import_float, is_spreadsheet_empty, parse_import_date
from app.services.tcc_computation import COMPUTED_TCC_COLUMN_KEYS, build_computed_tcc_field_values

_TCC_DATE_FIELDS = ("last_done_date", "next_due_date")
_TCC_FLOAT_FIELDS = (
    "component_limit_years",
    "component_limit_hours",
    "last_done_tach",
    "last_done_aftt",
    "remaining_years",
    "remaining_days",
    "remaining_tach",
    "remaining_aftt",
    "next_due_tach",
    "next_due_aftt",
)


def _sanitize_tcc_obj_for_db(obj: Any) -> None:
    """Ensure no pandas NaT/NaN reaches asyncpg on flush."""
    for name in _TCC_DATE_FIELDS:
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
    for name in _TCC_FLOAT_FIELDS:
        setattr(obj, name, coerce_import_float(getattr(obj, name, None)))


def _category_from_str(value: Optional[str]) -> Optional[TCCCategoryEnum]:
    if not value or not str(value).strip():
        return None
    s = str(value).strip()
    for e in TCCCategoryEnum:
        if e.value == s or e.name == s:
            return e
    return None


def _method_of_compliance_from_str(value: Optional[str]) -> Optional[MethodOfComplianceEnum]:
    if not value or not str(value).strip():
        return None
    s = str(value).strip()
    for e in MethodOfComplianceEnum:
        if e.value == s or e.name == s:
            return e
    return None


class MaintenanceTccImportHook(ImportHook):
    def apply_defaults(self, out: dict[str, Any], schema_fields: Set[str]) -> None:
        if "part_number" in schema_fields and out.get("part_number") is None:
            out["part_number"] = ""

    async def after_upsert(
        self,
        session,
        *,
        validated: BaseModel,
        existing,
        obj: Any,
        audit_account_id: Optional[int],
    ) -> None:
        aircraft_fk = getattr(obj, "aircraft_fk", None) or getattr(validated, "aircraft_fk", None)
        if aircraft_fk is None:
            return

        if getattr(obj, "part_number", None) is None:
            obj.part_number = ""

        _sanitize_tcc_obj_for_db(obj)

        # atl_ref: always from aircraft_technical_log.id where sequence_no matches import cell (same aircraft).
        atl_sequence = getattr(validated, "atl_sequence", None)
        if atl_sequence is not None and str(atl_sequence).strip():
            obj.atl_ref = await resolve_atl_id_by_sequence_no(
                session,
                aircraft_fk=aircraft_fk,
                sequence_no=atl_sequence,
            )
        else:
            obj.atl_ref = None

        category_enum = _category_from_str(getattr(obj, "category", None))
        obj.category = category_enum.value if category_enum else None

        component_moc = _method_of_compliance_from_str(
            getattr(obj, "component_method_of_compliance", None)
        )
        obj.component_method_of_compliance = (
            component_moc.value if component_moc else None
        )

        last_done_moc = _method_of_compliance_from_str(
            getattr(obj, "last_done_method_of_compliance", None)
        )
        obj.last_done_method_of_compliance = (
            last_done_moc.value if last_done_moc else None
        )

        computed = await build_computed_tcc_field_values(
            session,
            aircraft_fk=aircraft_fk,
            last_done_date=obj.last_done_date,
            last_done_tach=obj.last_done_tach,
            last_done_aftt=obj.last_done_aftt,
            component_limit_hours=obj.component_limit_hours,
            component_limit_years=obj.component_limit_years,
        )
        for key in COMPUTED_TCC_COLUMN_KEYS:
            setattr(obj, key, computed.get(key))
        _sanitize_tcc_obj_for_db(obj)
