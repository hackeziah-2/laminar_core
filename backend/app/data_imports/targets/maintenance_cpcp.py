from __future__ import annotations

from typing import Any, Dict, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.cpcp_excel_import import CPCP_EXCEL_COLUMN_MAPPING
from app.core.rbac_modules import MAINTENANCE_MODULE
from app.data_imports.definitions import ExcelImportTarget
from app.data_imports.form_utils import form_value, parse_form_optional_int
from app.data_imports.registry import register_import_target
from app.models.cpcp_monitoring import CPCPMonitoring
from app.repository.import_prerequisites import resolve_aircraft_id
from app.schemas.cpcp_monitoring_schema import CPCPMonitoringImportSchema


async def resolve_cpcp_import_context(
    session: AsyncSession,
    form: Mapping[str, Any],
) -> Dict[str, Any]:
    resolved_aircraft_id = await resolve_aircraft_id(
        session,
        aircraft_id=parse_form_optional_int(form_value(form, "aircraft_id")),
        registration=form_value(form, "registration"),
    )
    return {"aircraft_id": resolved_aircraft_id}


register_import_target(
    ExcelImportTarget(
        key="maintenance-cpcp",
        label="Maintenance CPCP",
        summary=(
            "Import CPCP monitoring rows for one aircraft (insert-only). "
            "Provide aircraft_id or registration. "
            "Column Sequence No. (or ATL Ref) must contain ATL sequence_no; "
            "we look up aircraft_technical_log by aircraft + sequence_no and set atl_ref to that row's id."
        ),
        model=CPCPMonitoring,
        schema=CPCPMonitoringImportSchema,
        unique_fields=[],
        hook_key="maintenance_cpcp",
        rbac_module=MAINTENANCE_MODULE,
        column_mapping=CPCP_EXCEL_COLUMN_MAPPING,
        integrity_error_messages={
            "aircraft_id": "Aircraft with this ID does not exist",
            "atl_ref": "ATL reference does not exist for this aircraft",
        },
        optional_form_fields=("aircraft_id", "registration"),
        resolve_context=resolve_cpcp_import_context,
        legacy_paths=("maintenance-cpcp",),
    )
)
