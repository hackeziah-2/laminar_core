from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Set

from app.services.excel_import.hooks.base import ImportHook


class AircraftImportHook(ImportHook):
    def __init__(self) -> None:
        self._registrations: list[str] = []

    def apply_defaults(self, out: Dict[str, Any], schema_fields: Set[str]) -> None:
        if "created_at" in schema_fields and not out.get("created_at"):
            out["created_at"] = datetime.now(timezone.utc)

    async def after_upsert(self, session, *, validated, existing, obj, audit_account_id) -> None:
        registration = getattr(existing or obj, "registration", None)
        if registration:
            self._registrations.append(registration)

    async def after_commit(self, session, *, context, audit_account_id) -> None:
        from app.repository.excel_import import sync_fleet_daily_updates_for_aircraft

        registrations = list(dict.fromkeys(self._registrations))
        if registrations:
            await sync_fleet_daily_updates_for_aircraft(
                session,
                registrations,
                audit_account_id=audit_account_id,
            )
