from __future__ import annotations

from app.services.excel_import.hooks.aircraft import AircraftImportHook
from app.services.excel_import.hooks.atl import AtlImportHook
from app.services.excel_import.hooks.base import ImportHook
from app.services.excel_import.hooks.maintenance_cpcp import MaintenanceCpcpImportHook
from app.services.excel_import.hooks.maintenance_tcc import MaintenanceTccImportHook

_ATL_HOOK = AtlImportHook()
_MAINTENANCE_TCC_HOOK = MaintenanceTccImportHook()
_MAINTENANCE_CPCP_HOOK = MaintenanceCpcpImportHook()


def get_import_hook(key: str) -> ImportHook:
    if key == "aircraft":
        return AircraftImportHook()
    if key == "aircraft_technical_log":
        return _ATL_HOOK
    if key == "maintenance_tcc":
        return _MAINTENANCE_TCC_HOOK
    if key == "maintenance_cpcp":
        return _MAINTENANCE_CPCP_HOOK
    return ImportHook()
