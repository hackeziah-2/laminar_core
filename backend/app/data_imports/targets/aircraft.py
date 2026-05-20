from __future__ import annotations

from app.core.rbac_modules import GENERAL_INFORMATION_MODULE
from app.data_imports.definitions import ExcelImportTarget
from app.data_imports.registry import register_import_target
from app.models.aircraft import Aircraft
from app.schemas.aircraft_schema import AircraftImportSchema

register_import_target(
    ExcelImportTarget(
        key="aircraft",
        label="Aircraft",
        summary="Import aircraft from Excel or CSV (unique on registration + MSN).",
        model=Aircraft,
        schema=AircraftImportSchema,
        unique_fields=["registration", "msn"],
        hook_key="aircraft",
        rbac_module=GENERAL_INFORMATION_MODULE,
        integrity_error_messages={
            "registration": "Aircraft with this registration already exists",
            "msn": "Aircraft with this MSN already exists",
        },
        legacy_paths=("aircraft",),
    )
)
