"""Resolve aircraft / ATL batch context before import (repository layer)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.ad_monitoring import ADMonitoring
from app.models.aircraft import Aircraft
from app.models.atl_batch import AtlBatch


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


async def ensure_atl_batch_exists(session: AsyncSession, batch_id: int) -> None:
    result = await session.execute(
        select(AtlBatch).where(
            AtlBatch.id == batch_id,
            AtlBatch.is_deleted.is_(False),
        )
    )
    if result.scalar_one_or_none() is None:
        raise NotFoundError("ATL batch not found")
