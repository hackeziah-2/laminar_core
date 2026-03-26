from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organizational_approval_history import OrganizationalApprovalHistory
from app.schemas.organizational_approval_history_schema import (
    OrganizationalApprovalHistoryCreate,
    OrganizationalApprovalHistoryRead,
)


async def list_organizational_approvals_history(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    certificate_fk: Optional[int] = None,
    sort: Optional[str] = "",
) -> Tuple[List[OrganizationalApprovalHistory], int]:
    stmt = select(OrganizationalApprovalHistory)
    if certificate_fk is not None:
        stmt = stmt.where(OrganizationalApprovalHistory.certificate_fk == certificate_fk)

    sortable = {
        "id": OrganizationalApprovalHistory.id,
        "certificate_fk": OrganizationalApprovalHistory.certificate_fk,
        "date_of_expiration": OrganizationalApprovalHistory.date_of_expiration,
        "created_at": OrganizationalApprovalHistory.created_at,
        "updated_at": OrganizationalApprovalHistory.updated_at,
    }
    if sort:
        for part in sort.split(","):
            desc = part.startswith("-")
            name = part.lstrip("-")
            col = sortable.get(name)
            if col is not None:
                stmt = stmt.order_by(col.desc() if desc else col.asc())
    else:
        stmt = stmt.order_by(OrganizationalApprovalHistory.created_at.desc())

    count_stmt = select(func.count()).select_from(OrganizationalApprovalHistory)
    if certificate_fk is not None:
        count_stmt = count_stmt.where(OrganizationalApprovalHistory.certificate_fk == certificate_fk)

    total = (await session.execute(count_stmt)).scalar()
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


async def get_organizational_approval_history(
    session: AsyncSession, history_id: int
) -> Optional[OrganizationalApprovalHistory]:
    result = await session.execute(
        select(OrganizationalApprovalHistory).where(OrganizationalApprovalHistory.id == history_id)
    )
    return result.scalar_one_or_none()


async def create_organizational_approval_history(
    session: AsyncSession,
    data: OrganizationalApprovalHistoryCreate,
) -> OrganizationalApprovalHistoryRead:
    obj = OrganizationalApprovalHistory(**data.dict())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return OrganizationalApprovalHistoryRead.from_orm(obj)
