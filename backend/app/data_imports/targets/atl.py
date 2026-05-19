from __future__ import annotations

from typing import Any, Dict, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.atl_excel_import import ATL_EXCEL_COLUMN_MAPPING
from app.core.exceptions import ValidationError
from app.core.rbac_modules import MAINTENANCE_MODULE
from app.data_imports.definitions import ExcelImportTarget
from app.data_imports.form_utils import form_value, parse_form_optional_int
from app.data_imports.registry import register_import_target
from app.models.aircraft_techinical_log import AircraftTechnicalLog
from app.repository.import_prerequisites import ensure_atl_batch_exists, resolve_aircraft_id
from app.schemas.aircraft_technical_log_schema import AircraftTechnicalLogImportSchema


async def resolve_atl_import_context(
    session: AsyncSession,
    form: Mapping[str, Any],
) -> Dict[str, Any]:
    batch_raw = form_value(form, "batch_id")
    resolved_batch_id = parse_form_optional_int(batch_raw)
    if resolved_batch_id is None:
        raise ValidationError(
            "batch_id is required and must be a valid integer (atl_batch.id)"
        )

    resolved_aircraft_id = await resolve_aircraft_id(
        session,
        aircraft_id=parse_form_optional_int(form_value(form, "aircraft_id")),
        registration=form_value(form, "registration"),
    )
    await ensure_atl_batch_exists(session, resolved_batch_id)
    return {
        "aircraft_fk": resolved_aircraft_id,
        "atl_batch_fk": resolved_batch_id,
    }


register_import_target(
    ExcelImportTarget(
        key="aircraft-technical-log",
        label="Aircraft Technical Log",
        summary=(
            "Import ATL rows for one aircraft and batch. "
            "Provide aircraft_id or registration plus required batch_id."
        ),
        model=AircraftTechnicalLog,
        schema=AircraftTechnicalLogImportSchema,
        unique_fields=["aircraft_fk", "sequence_no", "atl_batch_fk"],
        hook_key="aircraft_technical_log",
        rbac_module=MAINTENANCE_MODULE,
        column_mapping=ATL_EXCEL_COLUMN_MAPPING,
        integrity_error_messages={
            "aircraft_fk": "Aircraft with this ID does not exist",
            "sequence_no": "ATL upsert conflict for sequence_no / batch / aircraft",
            "atl_batch_fk": "ATL batch does not exist",
        },
        required_form_fields=("batch_id",),
        optional_form_fields=("aircraft_id", "registration"),
        resolve_context=resolve_atl_import_context,
        legacy_paths=("aircraft-technical-log",),
    )
)
