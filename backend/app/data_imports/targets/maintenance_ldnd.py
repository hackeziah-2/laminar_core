from __future__ import annotations

from typing import Any, Dict, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.ldnd_excel_import import LDND_EXCEL_COLUMN_MAPPING
from app.core.exceptions import ValidationError
from app.core.rbac_modules import MAINTENANCE_MODULE
from app.data_imports.definitions import ExcelImportTarget
from app.data_imports.form_utils import form_value, parse_form_optional_int
from app.data_imports.registry import register_import_target
from app.models.atl_monitoring import LDNDMonitoring
from app.repository.import_prerequisites import resolve_aircraft_id
from app.schemas.ldnd_monitoring_schema import LDNDMonitoringImportSchema


async def resolve_ldnd_import_context(
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
        key="maintenance-ldnd",
        label="Maintenance LDND",
        summary=(
            "Import LDND monitoring rows for one aircraft. "
            "Provide aircraft_id or registration."
        ),
        model=LDNDMonitoring,
        schema=LDNDMonitoringImportSchema,
        unique_fields=["aircraft_fk", "last_done_tach_done"],
        hook_key="maintenance_ldnd",
        rbac_module=MAINTENANCE_MODULE,
        column_mapping=LDND_EXCEL_COLUMN_MAPPING,
        integrity_error_messages={
            "aircraft_fk": "Aircraft with this ID does not exist",
            "last_done_tach_done": "LDND upsert conflict for last_done_tach_done / aircraft",
        },
        optional_form_fields=("aircraft_id", "registration"),
        resolve_context=resolve_ldnd_import_context,
        legacy_paths=("maintenance-ldnd",),
    )
)
