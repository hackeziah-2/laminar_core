from typing import Optional, List, Tuple

from fastapi import HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.organizational_approval import OrganizationalApproval
from app.models.certificate_category_type import CertificateCategoryType
from app.schemas.organizational_approval_schema import (
    OrganizationalApprovalCreate,
    OrganizationalApprovalUpdate,
    OrganizationalApprovalRead,
)


async def list_organizational_approvals(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    certificate_fk: Optional[int] = None,
    search: Optional[str] = None,
    sort: str = "",
) -> Tuple[List[OrganizationalApproval], int]:
    """List with pagination; filter by certificate_fk; search on number, web_link; sort by certification (name), date_of_expiration."""
    stmt = (
        select(OrganizationalApproval)
        .options(selectinload(OrganizationalApproval.certificate))
        .where(OrganizationalApproval.is_deleted == False)
    )
    if certificate_fk is not None:
        stmt = stmt.where(OrganizationalApproval.certificate_fk == certificate_fk)
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                OrganizationalApproval.number.ilike(q),
                OrganizationalApproval.web_link.ilike(q),
            )
        )

    # Sort: certificate_category_types__name / certification = certificate name (requires join), date_of_expiration, etc.
    sortable = {
        "id": OrganizationalApproval.id,
        "certificate_fk": OrganizationalApproval.certificate_fk,
        "date_of_expiration": OrganizationalApproval.date_of_expiration,
        "created_at": OrganizationalApproval.created_at,
        "updated_at": OrganizationalApproval.updated_at,
        "number": OrganizationalApproval.number,
    }
    name_sort_keys = ("certification", "certificate_category_types__name")
    sort_parts = [p.strip() for p in (sort or "").split(",") if p.strip()]
    if sort_parts:
        sort_names = [p.lstrip("-").strip() for p in sort_parts]
        if any(k in sort_names for k in name_sort_keys):
            stmt = stmt.outerjoin(OrganizationalApproval.certificate)
        order_parts = []
        for part in sort_parts:
            desc = part.startswith("-")
            name = part.lstrip("-").strip()
            if name in name_sort_keys:
                order_parts.append(
                    CertificateCategoryType.name.desc().nullslast() if desc else CertificateCategoryType.name.asc().nullslast()
                )
            elif name in sortable:
                order_parts.append(sortable[name].desc() if desc else sortable[name].asc())
        if order_parts:
            stmt = stmt.order_by(*order_parts)
    else:
        stmt = stmt.order_by(OrganizationalApproval.date_of_expiration.desc().nullslast())

    count_stmt = (
        select(func.count())
        .select_from(OrganizationalApproval)
        .where(OrganizationalApproval.is_deleted == False)
    )
    if certificate_fk is not None:
        count_stmt = count_stmt.where(OrganizationalApproval.certificate_fk == certificate_fk)
    if search and search.strip():
        q = f"%{search.strip()}%"
        count_stmt = count_stmt.where(
            or_(
                OrganizationalApproval.number.ilike(q),
                OrganizationalApproval.web_link.ilike(q),
            )
        )
    total = (await session.execute(count_stmt)).scalar()
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


async def get_organizational_approval(
    session: AsyncSession,
    approval_id: int,
) -> Optional[OrganizationalApproval]:
    """Get one by ID."""
    result = await session.execute(
        select(OrganizationalApproval)
        .options(selectinload(OrganizationalApproval.certificate))
        .where(OrganizationalApproval.id == approval_id)
        .where(OrganizationalApproval.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def create_organizational_approval(
    session: AsyncSession,
    data: OrganizationalApprovalCreate,
) -> OrganizationalApprovalRead:
    """Create organizational approval (no file upload)."""
    approval_data = data.dict()
    try:
        obj = OrganizationalApproval(**approval_data)
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
        await session.refresh(obj, ["certificate"])
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create organizational approval: {str(e)}")
    return OrganizationalApprovalRead.from_orm(obj)


async def update_organizational_approval(
    session: AsyncSession,
    approval_id: int,
    data: OrganizationalApprovalUpdate,
) -> Optional[OrganizationalApprovalRead]:
    """Update organizational approval (no file upload)."""
    result = await session.execute(
        select(OrganizationalApproval)
        .options(selectinload(OrganizationalApproval.certificate))
        .where(OrganizationalApproval.id == approval_id)
        .where(OrganizationalApproval.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    update_data = data.dict(exclude_unset=True)
    for k, v in update_data.items():
        setattr(obj, k, v)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    await session.refresh(obj, ["certificate"])
    return OrganizationalApprovalRead.from_orm(obj)


async def soft_delete_organizational_approval(
    session: AsyncSession,
    approval_id: int,
) -> bool:
    """Soft delete."""
    obj = await session.get(OrganizationalApproval, approval_id)
    if not obj or obj.is_deleted:
        return False
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True
