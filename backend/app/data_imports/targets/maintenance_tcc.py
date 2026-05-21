from __future__ import annotations

from typing import Any, Dict, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.tcc_excel_import import TCC_EXCEL_COLUMN_MAPPING
from app.core.rbac_modules import MAINTENANCE_MODULE
from app.data_imports.definitions import ExcelImportTarget
from app.data_imports.form_utils import form_value, parse_form_optional_int
from app.data_imports.registry import register_import_target
from app.models.tcc_maintenance import TCCMaintenance
from app.repository.import_prerequisites import resolve_aircraft_id
from app.schemas.tcc_maintenance_schema import TCCMaintenanceImportSchema


async def resolve_tcc_import_context(
    session: AsyncSession,
    form: Mapping[str, Any],
) -> Dict[str, Any]:
    resolved_aircraft_id = await resolve_aircraft_id(
        session,
        aircraft_id=parse_form_optional_int(form_value(form, "aircraft_id")),
        registration=form_value(form, "registration"),
    )
    return {"aircraft_fk": resolved_aircraft_id}


register_import_target(
    ExcelImportTarget(
        key="maintenance-tcc",
        label="Maintenance TCC",
        summary=(
            "Import TCC maintenance rows for one aircraft (insert-only). "
            "Provide aircraft_id or registration. "
            "Column ATL Ref or Sequence No must contain the ATL sequence number; "
            "we look up aircraft_technical_log by aircraft + sequence_no and set atl_ref to that row's id."
        ),
        model=TCCMaintenance,
        schema=TCCMaintenanceImportSchema,
        unique_fields=[],
        hook_key="maintenance_tcc",
        rbac_module=MAINTENANCE_MODULE,
        column_mapping=TCC_EXCEL_COLUMN_MAPPING,
        integrity_error_messages={
            "aircraft_fk": "Aircraft with this ID does not exist",
            "atl_ref": "ATL reference does not exist for this aircraft",
        },
        optional_form_fields=("aircraft_id", "registration"),
        resolve_context=resolve_tcc_import_context,
        legacy_paths=("maintenance-tcc",),
    )
)
