from __future__ import annotations

from app.services.excel_import.hooks.aircraft import AircraftImportHook
from app.services.excel_import.hooks.atl import AtlImportHook
from app.services.excel_import.hooks.base import ImportHook

_ATL_HOOK = AtlImportHook()


def get_import_hook(key: str) -> ImportHook:
    if key == "aircraft":
        return AircraftImportHook()
    if key == "aircraft_technical_log":
        return _ATL_HOOK
    return ImportHook()
