"""Preloaded reference data for ATL import (single round-trip per resource)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Set

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import AccountInformation
from app.models.aircraft_techinical_log import AircraftTechnicalLog


@dataclass
class AtlImportReferences:
    """In-memory caches used during validation and bulk persist."""

    existing_by_sequence: Dict[str, AircraftTechnicalLog] = field(default_factory=dict)
    valid_account_ids: Set[int] = field(default_factory=set)

    def is_existing(self, sequence_no: str) -> bool:
        return sequence_no in self.existing_by_sequence


async def load_atl_import_references(
    session: AsyncSession,
    *,
    aircraft_fk: int,
    atl_batch_fk: int,
    account_ids: Set[int],
) -> AtlImportReferences:
    """Load existing ATL rows and referenced account IDs in two queries (no row loop)."""
    existing_result = await session.execute(
        select(AircraftTechnicalLog).where(
            AircraftTechnicalLog.aircraft_fk == aircraft_fk,
            AircraftTechnicalLog.atl_batch_fk == atl_batch_fk,
            AircraftTechnicalLog.is_deleted.is_(False),
        )
    )
    existing_by_sequence = {
        row.sequence_no: row for row in existing_result.scalars().all()
    }

    valid_account_ids: Set[int] = set()
    if account_ids:
        account_result = await session.execute(
            select(AccountInformation.id).where(
                AccountInformation.id.in_(account_ids)
            )
        )
        valid_account_ids = set(account_result.scalars().all())

    return AtlImportReferences(
        existing_by_sequence=existing_by_sequence,
        valid_account_ids=valid_account_ids,
    )


def collect_account_ids_from_validated_rows(validated_rows) -> Set[int]:
    fields = (
        "remark_person",
        "actiontaken_person",
        "pilot_fk",
        "maintenance_fk",
        "pilot_accepted_by",
        "rts_signed_by",
    )
    ids: Set[int] = set()
    for _, validated in validated_rows:
        for field_name in fields:
            value = getattr(validated, field_name, None)
            if value is not None:
                ids.add(int(value))
    return ids
