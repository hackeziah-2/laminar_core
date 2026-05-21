from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel

from app.services.atl_import_normalize import (
    merge_atl_continuation_records,
    normalize_atl_import_row,
)
from app.services.excel_import.hooks.base import ImportHook


class AtlImportHook(ImportHook):
    def preprocess_records(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return merge_atl_continuation_records(records)

    def transform_row(self, merged: Dict[str, Any]) -> None:
        normalize_atl_import_row(merged)

    async def after_upsert(
        self,
        session,
        *,
        validated: BaseModel,
        existing,
        obj,
        audit_account_id,
    ) -> None:
        from app.repository.aircraft_technical_log import _replace_atl_component_parts

        parts = getattr(validated, "component_parts", None)
        if parts is None:
            return
        target = existing or obj
        atl_id = getattr(target, "id", None)
        if atl_id is None:
            await session.flush()
            atl_id = obj.id
        await _replace_atl_component_parts(
            session=session,
            atl_id=atl_id,
            component_parts=list(parts),
            audit_account_id=audit_account_id,
        )
