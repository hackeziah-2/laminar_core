from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import set_audit_fields
from app.models.aircraft_statutory_certificate import CategoryTypeEnum
from app.models.aircraft_statutory_certificate_history import AircraftStatutoryCertificateHistory
from app.schemas.aircraft_statutory_certificate_history_schema import (
    AircraftStatutoryCertificateHistoryCreate,
    AircraftStatutoryCertificateHistoryRead,
)


async def list_aircraft_statutory_certificates_history(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    aircraft_fk: Optional[int] = None,
    asc_history: Optional[int] = None,
    category_type: Optional[CategoryTypeEnum] = None,
    sort: Optional[str] = "",
) -> Tuple[List[AircraftStatutoryCertificateHistory], int]:
    stmt = select(AircraftStatutoryCertificateHistory)
    if aircraft_fk is not None:
        stmt = stmt.where(AircraftStatutoryCertificateHistory.aircraft_fk == aircraft_fk)
    if asc_history is not None:
        stmt = stmt.where(AircraftStatutoryCertificateHistory.asc_history == asc_history)
    if category_type is not None:
        stmt = stmt.where(AircraftStatutoryCertificateHistory.category_type == category_type)

    sortable = {
        "id": AircraftStatutoryCertificateHistory.id,
        "aircraft_fk": AircraftStatutoryCertificateHistory.aircraft_fk,
        "asc_history": AircraftStatutoryCertificateHistory.asc_history,
        "category_type": AircraftStatutoryCertificateHistory.category_type,
        "date_of_expiration": AircraftStatutoryCertificateHistory.date_of_expiration,
        "created_at": AircraftStatutoryCertificateHistory.created_at,
        "updated_at": AircraftStatutoryCertificateHistory.updated_at,
    }
    if sort:
        for part in sort.split(","):
            desc = part.startswith("-")
            name = part.lstrip("-")
            col = sortable.get(name)
            if col is not None:
                stmt = stmt.order_by(col.desc() if desc else col.asc())
    else:
        stmt = stmt.order_by(AircraftStatutoryCertificateHistory.created_at.desc())

    count_stmt = select(func.count()).select_from(AircraftStatutoryCertificateHistory)
    if aircraft_fk is not None:
        count_stmt = count_stmt.where(AircraftStatutoryCertificateHistory.aircraft_fk == aircraft_fk)
    if asc_history is not None:
        count_stmt = count_stmt.where(AircraftStatutoryCertificateHistory.asc_history == asc_history)
    if category_type is not None:
        count_stmt = count_stmt.where(AircraftStatutoryCertificateHistory.category_type == category_type)

    total = (await session.execute(count_stmt)).scalar()
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


async def get_aircraft_statutory_certificate_history(
    session: AsyncSession, history_id: int
) -> Optional[AircraftStatutoryCertificateHistory]:
    result = await session.execute(
        select(AircraftStatutoryCertificateHistory).where(AircraftStatutoryCertificateHistory.id == history_id)
    )
    return result.scalar_one_or_none()


async def create_aircraft_statutory_certificate_history(
    session: AsyncSession,
    data: AircraftStatutoryCertificateHistoryCreate,
    *,
    audit_account_id: Optional[int] = None,
    commit: bool = True,
) -> AircraftStatutoryCertificateHistoryRead:
    payload = data.dict()
    # asc_history = aircraft_statutory_certificates.id
    if payload.get("asc_history") is None:
        from app.repository.aircraft_statutory_certificate import get_existing_record

        cert = await get_existing_record(
            session, payload["aircraft_fk"], data.category_type
        )
        if cert is not None:
            payload["asc_history"] = cert.id
    obj = AircraftStatutoryCertificateHistory(**payload)
    session.add(obj)
    if audit_account_id is not None:
        await set_audit_fields(obj, audit_account_id, is_create=True)
    if commit:
        await session.commit()
        await session.refresh(obj)
    else:
        await session.flush()
        await session.refresh(obj)
    return AircraftStatutoryCertificateHistoryRead.from_orm(obj)
