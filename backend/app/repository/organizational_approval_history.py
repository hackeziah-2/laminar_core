from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import set_audit_fields
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
    oa_history: Optional[int] = None,
    sort: Optional[str] = "",
) -> Tuple[List[OrganizationalApprovalHistory], int]:
    stmt = select(OrganizationalApprovalHistory)
    if certificate_fk is not None:
        stmt = stmt.where(OrganizationalApprovalHistory.certificate_fk == certificate_fk)
    if oa_history is not None:
        stmt = stmt.where(OrganizationalApprovalHistory.oa_history == oa_history)

    sortable = {
        "id": OrganizationalApprovalHistory.id,
        "certificate_fk": OrganizationalApprovalHistory.certificate_fk,
        "oa_history": OrganizationalApprovalHistory.oa_history,
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
    if oa_history is not None:
        count_stmt = count_stmt.where(OrganizationalApprovalHistory.oa_history == oa_history)

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
    *,
    audit_account_id: Optional[int] = None,
    commit: bool = True,
) -> OrganizationalApprovalHistoryRead:
    payload = data.dict()
    if payload.get("oa_history") is None:
        from app.repository.organizational_approval import (
            get_organizational_approval_id_by_natural_key,
        )

        approval_id = await get_organizational_approval_id_by_natural_key(
            session,
            payload["certificate_fk"],
            payload.get("date_of_expiration"),
            payload.get("number"),
        )
        if approval_id is not None:
            payload["oa_history"] = approval_id
    obj = OrganizationalApprovalHistory(**payload)
    session.add(obj)
    if audit_account_id is not None:
        await set_audit_fields(obj, audit_account_id, is_create=True)
    if commit:
        await session.commit()
        await session.refresh(obj)
    else:
        await session.flush()
        await session.refresh(obj)
    return OrganizationalApprovalHistoryRead.from_orm(obj)
