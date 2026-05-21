from __future__ import annotations

from typing import Any, Dict, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.ad_excel_import import AD_EXCEL_COLUMN_MAPPING
from app.core.rbac_modules import MAINTENANCE_MODULE
from app.data_imports.definitions import ExcelImportTarget
from app.data_imports.form_utils import form_value, parse_form_optional_int
from app.data_imports.registry import register_import_target
from app.models.ad_monitoring import ADMonitoring
from app.repository.import_prerequisites import resolve_aircraft_id
from app.schemas.ad_monitoring_schema import ADMonitoringImportSchema


async def resolve_ad_import_context(
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
        key="maintenance-ad",
        label="Maintenance AD",
        summary=(
            "Import AD monitoring rows for one aircraft. "
            "Provide aircraft_id or registration."
        ),
        model=ADMonitoring,
        schema=ADMonitoringImportSchema,
        unique_fields=["ad_number"],
        hook_key="maintenance_ad",
        rbac_module=MAINTENANCE_MODULE,
        column_mapping=AD_EXCEL_COLUMN_MAPPING,
        integrity_error_messages={
            "aircraft_fk": "Aircraft with this ID does not exist",
            "ad_number": "AD upsert conflict for ad_number / aircraft",
        },
        optional_form_fields=("aircraft_id", "registration"),
        resolve_context=resolve_ad_import_context,
        legacy_paths=("maintenance-ad",),
    )
)
