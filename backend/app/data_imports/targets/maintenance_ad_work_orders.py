from __future__ import annotations

from typing import Any, Dict, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.ad_work_order_excel_import import AD_WORK_ORDER_EXCEL_COLUMN_MAPPING
from app.core.rbac_modules import MAINTENANCE_MODULE
from app.data_imports.definitions import ExcelImportTarget
from app.data_imports.form_utils import form_value, parse_form_optional_int
from app.data_imports.registry import register_import_target
from app.models.ad_monitoring import WorkOrderADMonitoring
from app.repository.import_prerequisites import resolve_ad_monitoring_id
from app.schemas.ad_monitoring_schema import WorkOrderADMonitoringImportSchema


async def resolve_ad_work_order_import_context(
    session: AsyncSession,
    form: Mapping[str, Any],
) -> Dict[str, Any]:
    ad_monitoring_id = parse_form_optional_int(form_value(form, "ad_monitoring_id"))
    if ad_monitoring_id is None:
        ad_monitoring_id = parse_form_optional_int(form_value(form, "ad_monitoring_fk"))
    resolved_ad_monitoring_id = await resolve_ad_monitoring_id(
        session,
        ad_monitoring_id=ad_monitoring_id,
    )
    return {"ad_monitoring_fk": resolved_ad_monitoring_id}


register_import_target(
    ExcelImportTarget(
        key="maintenance-ad-work-orders",
        label="Maintenance AD Work Orders",
        summary=(
            "Import work orders for one AD monitoring record. "
            "Provide ad_monitoring_id (or ad_monitoring_fk)."
        ),
        model=WorkOrderADMonitoring,
        schema=WorkOrderADMonitoringImportSchema,
        unique_fields=["work_order_number"],
        hook_key="maintenance_ad_work_orders",
        rbac_module=MAINTENANCE_MODULE,
        column_mapping=AD_WORK_ORDER_EXCEL_COLUMN_MAPPING,
        integrity_error_messages={
            "ad_monitoring_fk": "AD monitoring record does not exist",
            "work_order_number": "Work order upsert conflict for work_order_number",
        },
        optional_form_fields=("ad_monitoring_id", "ad_monitoring_fk"),
        resolve_context=resolve_ad_work_order_import_context,
        legacy_paths=("maintenance-ad-work-orders",),
    )
)
