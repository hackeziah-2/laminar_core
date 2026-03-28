from datetime import date
from typing import Optional, List, Tuple

from fastapi import HTTPException, status
from sqlalchemy import and_, select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import set_audit_fields
from app.models.organizational_approval import OrganizationalApproval
from app.models.organizational_approval_history import OrganizationalApprovalHistory
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
                col = sortable[name]
                if name == "date_of_expiration":
                    order_parts.append(
                        col.desc().nullslast() if desc else col.asc().nullslast()
                    )
                else:
                    order_parts.append(col.desc() if desc else col.asc())
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


async def get_organizational_approval_id_by_natural_key(
    session: AsyncSession,
    certificate_fk: int,
    date_of_expiration: Optional[date],
    number: Optional[str],
) -> Optional[int]:
    """Return organizational_approvals.id for a non-deleted row matching certificate, expiration, and number (NULL-safe)."""
    conditions = [
        OrganizationalApproval.certificate_fk == certificate_fk,
        OrganizationalApproval.is_deleted == False,
    ]
    if date_of_expiration is None:
        conditions.append(OrganizationalApproval.date_of_expiration.is_(None))
    else:
        conditions.append(OrganizationalApproval.date_of_expiration == date_of_expiration)
    if number is None:
        conditions.append(OrganizationalApproval.number.is_(None))
    else:
        conditions.append(OrganizationalApproval.number == number)
    result = await session.execute(
        select(OrganizationalApproval.id).where(and_(*conditions)).limit(1)
    )
    return result.scalar_one_or_none()


async def organizational_approval_duplicate_exists(
    session: AsyncSession,
    certificate_fk: int,
    date_of_expiration: Optional[date],
    number: Optional[str],
) -> bool:
    """True if a non-deleted row matches certificate, expiration date, and number (NULL-safe)."""
    conditions = [
        OrganizationalApproval.certificate_fk == certificate_fk,
        OrganizationalApproval.is_deleted == False,
    ]
    if date_of_expiration is None:
        conditions.append(OrganizationalApproval.date_of_expiration.is_(None))
    else:
        conditions.append(OrganizationalApproval.date_of_expiration == date_of_expiration)
    if number is None:
        conditions.append(OrganizationalApproval.number.is_(None))
    else:
        conditions.append(OrganizationalApproval.number == number)
    result = await session.execute(
        select(OrganizationalApproval.id).where(and_(*conditions)).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def get_existing_organizational_approval(
    session: AsyncSession,
    certificate_fk: int,
    number: Optional[str],
) -> Optional[OrganizationalApproval]:
    """One non-deleted row matching certificate (approval type) and number (NULL-safe)."""
    conditions = [
        OrganizationalApproval.certificate_fk == certificate_fk,
        OrganizationalApproval.is_deleted == False,
    ]
    if number is None:
        conditions.append(OrganizationalApproval.number.is_(None))
    else:
        conditions.append(OrganizationalApproval.number == number)
    result = await session.execute(
        select(OrganizationalApproval)
        .options(selectinload(OrganizationalApproval.certificate))
        .where(and_(*conditions))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_organizational_approval(
    session: AsyncSession,
    data: OrganizationalApprovalCreate,
    *,
    audit_account_id: Optional[int] = None,
) -> OrganizationalApprovalRead:
    """Create organizational approval, or snapshot prior state to history and update if one exists for certificate + number."""
    try:
        async with session.begin():
            if await organizational_approval_duplicate_exists(
                session,
                data.certificate_fk,
                data.date_of_expiration,
                data.number,
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Entry already exists",
                )
            existing = await get_existing_organizational_approval(
                session, data.certificate_fk, data.number
            )
            if existing:
                snapshot = OrganizationalApprovalHistory(
                    certificate_fk=existing.certificate_fk,
                    oa_history=existing.id,
                    number=existing.number,
                    date_of_expiration=existing.date_of_expiration,
                    web_link=existing.web_link,
                )
                session.add(snapshot)
                existing.date_of_expiration = data.date_of_expiration
                existing.web_link = data.web_link
                existing.is_withhold = False
                session.add(existing)
                obj = existing
                if audit_account_id is not None:
                    await set_audit_fields(snapshot, audit_account_id, is_create=True)
                    await set_audit_fields(existing, audit_account_id, is_create=False)
            else:
                obj = OrganizationalApproval(**data.dict())
                session.add(obj)
                if audit_account_id is not None:
                    await set_audit_fields(obj, audit_account_id, is_create=True)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Failed to create organizational approval: {str(e)}",
        )
    await session.refresh(obj)
    await session.refresh(obj, ["certificate"])
    return OrganizationalApprovalRead.from_orm(obj)


async def update_organizational_approval(
    session: AsyncSession,
    approval_id: int,
    data: OrganizationalApprovalUpdate,
    *,
    audit_account_id: Optional[int] = None,
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
    if audit_account_id is not None:
        await set_audit_fields(obj, audit_account_id, is_create=False)
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
