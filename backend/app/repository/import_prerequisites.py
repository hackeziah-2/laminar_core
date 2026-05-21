"""Resolve aircraft / ATL batch context before import (repository layer)."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.ad_monitoring import ADMonitoring
from app.models.aircraft import Aircraft
from app.models.aircraft_techinical_log import AircraftTechnicalLog
from app.models.atl_batch import AtlBatch
from app.schemas.aircraft_technical_log_schema import normalize_sequence_no_digits_only


async def resolve_aircraft_id(
    session: AsyncSession,
    *,
    aircraft_id: Optional[int] = None,
    registration: Optional[str] = None,
) -> int:
    if aircraft_id is not None:
        result = await session.execute(
            select(Aircraft).where(
                Aircraft.id == aircraft_id,
                Aircraft.is_deleted.is_(False),
            )
        )
        if result.scalar_one_or_none() is None:
            raise NotFoundError("Aircraft with this ID not found")
        return aircraft_id

    reg = (registration or "").strip()
    if reg:
        result = await session.execute(
            select(Aircraft).where(
                Aircraft.registration.ilike(reg),
                Aircraft.is_deleted.is_(False),
            )
        )
        aircraft = result.scalar_one_or_none()
        if aircraft is None:
            raise NotFoundError(f"Aircraft with registration '{reg}' not found")
        return aircraft.id

    raise ValidationError("Provide either aircraft_id or registration")


async def resolve_ad_monitoring_id(
    session: AsyncSession,
    *,
    ad_monitoring_id: Optional[int] = None,
) -> int:
    if ad_monitoring_id is None:
        raise ValidationError("Provide ad_monitoring_id (or ad_monitoring_fk)")
    result = await session.execute(
        select(ADMonitoring).where(
            ADMonitoring.id == ad_monitoring_id,
            ADMonitoring.is_deleted.is_(False),
        )
    )
    if result.scalar_one_or_none() is None:
        raise NotFoundError("AD monitoring record not found")
    return ad_monitoring_id


def _sequence_no_from_import_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, float):
        if value != value or not value:  # NaN or zero-ish empty
            return None
        if value.is_integer():
            return str(int(value))
        return str(value).strip()
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    s = str(value).strip()
    if not s or s.upper() in ("-", "NA", "N/A"):
        return None
    return s


async def resolve_atl_id_by_sequence_no(
    session: AsyncSession,
    *,
    aircraft_fk: int,
    sequence_no: Any,
) -> Optional[int]:
    """Return first matching ``aircraft_technical_log.id`` by aircraft + sequence_no."""
    raw = _sequence_no_from_import_value(sequence_no)
    if raw is None:
        return None
    normalized = normalize_sequence_no_digits_only(raw)
    if not normalized:
        return None
    result = await session.execute(
        select(AircraftTechnicalLog)
        .where(AircraftTechnicalLog.is_deleted.is_(False))
        .where(AircraftTechnicalLog.aircraft_fk == aircraft_fk)
        .where(AircraftTechnicalLog.sequence_no == normalized)
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row.id if row is not None else None


async def ensure_atl_batch_exists(session: AsyncSession, batch_id: int) -> None:
    result = await session.execute(
        select(AtlBatch).where(
            AtlBatch.id == batch_id,
            AtlBatch.is_deleted.is_(False),
        )
    )
    if result.scalar_one_or_none() is None:
        raise NotFoundError("ATL batch not found")
