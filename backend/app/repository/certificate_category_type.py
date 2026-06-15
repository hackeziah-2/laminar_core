from typing import Optional, List, Tuple

from fastapi import HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import set_audit_fields
from app.models.account import AccountInformation
from app.models.audit_log import AuditAction
from app.models.certificate_category_type import CertificateCategoryType
from app.schemas.certificate_category_type_schema import (
    CertificateCategoryTypeCreate,
    CertificateCategoryTypeUpdate,
    CertificateCategoryTypeRead,
)
from app.services.audit_trail_service import create_audit_log, serialize_audit_data


async def create_certificate_category_type(
    session: AsyncSession,
    data: CertificateCategoryTypeCreate,
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> CertificateCategoryTypeRead:
    """Create a new Certificate Category Type."""
    result = await session.execute(
        select(CertificateCategoryType).where(
            CertificateCategoryType.name == data.name,
            CertificateCategoryType.is_deleted == False,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Certificate category type with this name already exists",
        )
    obj = CertificateCategoryType(**data.dict())
    session.add(obj)
    if audit_account_id is not None:
        await set_audit_fields(obj, audit_account_id, is_create=True)
    await session.commit()
    await session.refresh(obj)

    if audit_module_name and audit_table_name:
        await create_audit_log(
            db=session,
            module_name=audit_module_name,
            table_name=audit_table_name,
            record_id=obj.id,
            action=AuditAction.CREATE,
            old_data=None,
            new_data=obj,
            current_user=audit_user,
            request=audit_request,
        )

    return CertificateCategoryTypeRead.from_orm(obj)


async def get_certificate_category_type(
    session: AsyncSession,
    category_id: int,
) -> Optional[CertificateCategoryTypeRead]:
    """Get a Certificate Category Type by ID."""
    result = await session.execute(
        select(CertificateCategoryType)
        .where(CertificateCategoryType.id == category_id)
        .where(CertificateCategoryType.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    return CertificateCategoryTypeRead.from_orm(obj)


async def update_certificate_category_type(
    session: AsyncSession,
    category_id: int,
    data: CertificateCategoryTypeUpdate,
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> Optional[CertificateCategoryTypeRead]:
    """Update a Certificate Category Type."""
    obj = await session.get(CertificateCategoryType, category_id)
    if not obj or obj.is_deleted:
        return None
    old_data_snapshot = serialize_audit_data(obj)
    update_data = data.dict(exclude_unset=True)
    if "name" in update_data:
        result = await session.execute(
            select(CertificateCategoryType).where(
                CertificateCategoryType.name == update_data["name"],
                CertificateCategoryType.id != category_id,
                CertificateCategoryType.is_deleted == False,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Certificate category type with this name already exists",
            )
    for k, v in update_data.items():
        setattr(obj, k, v)
    session.add(obj)
    if audit_account_id is not None:
        await set_audit_fields(obj, audit_account_id, is_create=False)
    await session.commit()
    await session.refresh(obj)

    if audit_module_name and audit_table_name:
        await create_audit_log(
            db=session,
            module_name=audit_module_name,
            table_name=audit_table_name,
            record_id=obj.id,
            action=AuditAction.UPDATE,
            old_data=old_data_snapshot,
            new_data=obj,
            current_user=audit_user,
            request=audit_request,
        )

    return CertificateCategoryTypeRead.from_orm(obj)


async def list_certificate_category_types(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    sort: str = "",
) -> Tuple[List[CertificateCategoryType], int]:
    """List Certificate Category Types with pagination."""
    stmt = (
        select(CertificateCategoryType)
        .where(CertificateCategoryType.is_deleted == False)
    )
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(CertificateCategoryType.name.ilike(q))

    sortable = {
        "id": CertificateCategoryType.id,
        "name": CertificateCategoryType.name,
        "created_at": CertificateCategoryType.created_at,
        "updated_at": CertificateCategoryType.updated_at,
    }
    if sort:
        for part in sort.split(","):
            desc = part.startswith("-")
            name = part.lstrip("-")
            col = sortable.get(name)
            if col is not None:
                stmt = stmt.order_by(col.desc() if desc else col.asc())
    else:
        stmt = stmt.order_by(CertificateCategoryType.name.asc())

    count_stmt = (
        select(func.count())
        .select_from(CertificateCategoryType)
        .where(CertificateCategoryType.is_deleted == False)
    )
    if search and search.strip():
        q = f"%{search.strip()}%"
        count_stmt = count_stmt.where(CertificateCategoryType.name.ilike(q))
    total = (await session.execute(count_stmt)).scalar()
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


async def get_all_certificate_category_types_list(
    session: AsyncSession,
) -> List[CertificateCategoryType]:
    """Get all (no pagination, for dropdowns)."""
    result = await session.execute(
        select(CertificateCategoryType)
        .where(CertificateCategoryType.is_deleted == False)
        .order_by(CertificateCategoryType.name.asc())
    )
    return list(result.scalars().all())


async def soft_delete_certificate_category_type(
    session: AsyncSession,
    category_id: int,
    *,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> bool:
    """Soft delete a Certificate Category Type."""
    obj = await session.get(CertificateCategoryType, category_id)
    if not obj or obj.is_deleted:
        return False
    old_data_snapshot = serialize_audit_data(obj)
    obj.soft_delete()
    session.add(obj)
    await session.commit()

    if audit_module_name and audit_table_name:
        await create_audit_log(
            db=session,
            module_name=audit_module_name,
            table_name=audit_table_name,
            record_id=category_id,
            action=AuditAction.DELETE,
            old_data=old_data_snapshot,
            new_data=None,
            current_user=audit_user,
            request=audit_request,
        )

    return True
