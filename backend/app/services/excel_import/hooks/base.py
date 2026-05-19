"""Import hook protocol for entity-specific spreadsheet behavior."""
from __future__ import annotations

from abc import ABC
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession


class ImportHook(ABC):
    """Optional overrides for a target model during Excel import."""

    def preprocess_records(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return records

    def transform_row(self, merged: Dict[str, Any]) -> None:
        """Mutate merged row dict in place before field extraction."""

    def apply_defaults(self, out: Dict[str, Any], schema_fields: Set[str]) -> None:
        """Set default values on the schema-bound dict."""

    async def after_upsert(
        self,
        session: AsyncSession,
        *,
        validated: BaseModel,
        existing: Any,
        obj: Any,
        audit_account_id: Optional[int],
    ) -> None:
        """Called after each row is inserted or updated (within the write transaction)."""

    async def after_commit(
        self,
        session: AsyncSession,
        *,
        context: Dict[str, Any],
        audit_account_id: Optional[int],
    ) -> None:
        """Called once after a successful commit (e.g. fleet daily update sync)."""
