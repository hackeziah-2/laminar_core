from typing import Optional, List, Tuple

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.personnel_authorization import PersonnelAuthorization
from app.models.account import AccountInformation
from app.schemas.personnel_authorization_schema import (
    PersonnelAuthorizationCreate,
    PersonnelAuthorizationUpdate,
    PersonnelAuthorizationRead,
)


async def list_personnel_authorizations(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    sort: str = "",
) -> Tuple[List[PersonnelAuthorization], int]:
    """List with pagination; sort by date_of_expiration (auth_expiry_date) ASC/DESC; search by account_information name (first_name, last_name)."""
    stmt = (
        select(PersonnelAuthorization)
        .options(
            selectinload(PersonnelAuthorization.account_information),
            selectinload(PersonnelAuthorization.authorization_scope_cessna),
            selectinload(PersonnelAuthorization.authorization_scope_baron),
            selectinload(PersonnelAuthorization.authorization_scope_others),
        )
        .where(PersonnelAuthorization.is_deleted == False)
    )
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.join(PersonnelAuthorization.account_information)
        stmt = stmt.where(
            or_(
                AccountInformation.first_name.ilike(q),
                AccountInformation.last_name.ilike(q),
            )
        )

    sortable = {
        "id": PersonnelAuthorization.id,
        "account_information_id": PersonnelAuthorization.account_information_id,
        "auth_initial_doi": PersonnelAuthorization.auth_initial_doi,
        "auth_issue_date": PersonnelAuthorization.auth_issue_date,
        "auth_expiry_date": PersonnelAuthorization.auth_expiry_date,
        "date_of_expiration": PersonnelAuthorization.auth_expiry_date,
        "caap_license_expiry": PersonnelAuthorization.caap_license_expiry,
        "human_factors_training_expiry": PersonnelAuthorization.human_factors_training_expiry,
        "type_training_expiry_cessna": PersonnelAuthorization.type_training_expiry_cessna,
        "type_training_expiry_baron": PersonnelAuthorization.type_training_expiry_baron,
        "created_at": PersonnelAuthorization.created_at,
        "updated_at": PersonnelAuthorization.updated_at,
    }
    if sort:
        order_parts = []
        for part in sort.split(","):
            desc = part.startswith("-")
            name = part.lstrip("-")
            col = sortable.get(name)
            if col is not None:
                order_parts.append(col.desc() if desc else col.asc())
        if order_parts:
            stmt = stmt.order_by(*order_parts)
    else:
        stmt = stmt.order_by(
            PersonnelAuthorization.auth_expiry_date.desc().nullslast()
        )

    count_stmt = (
        select(func.count())
        .select_from(PersonnelAuthorization)
        .where(PersonnelAuthorization.is_deleted == False)
    )
    if search and search.strip():
        q = f"%{search.strip()}%"
        count_stmt = count_stmt.join(
            PersonnelAuthorization.account_information
        ).where(
            or_(
                AccountInformation.first_name.ilike(q),
                AccountInformation.last_name.ilike(q),
            )
        )
    total = (await session.execute(count_stmt)).scalar()
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


async def get_personnel_authorization(
    session: AsyncSession,
    auth_id: int,
) -> Optional[PersonnelAuthorization]:
    result = await session.execute(
        select(PersonnelAuthorization)
        .options(
            selectinload(PersonnelAuthorization.account_information),
            selectinload(PersonnelAuthorization.authorization_scope_cessna),
            selectinload(PersonnelAuthorization.authorization_scope_baron),
            selectinload(PersonnelAuthorization.authorization_scope_others),
        )
        .where(PersonnelAuthorization.id == auth_id)
        .where(PersonnelAuthorization.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def create_personnel_authorization(
    session: AsyncSession,
    data: PersonnelAuthorizationCreate,
) -> PersonnelAuthorizationRead:
    obj = PersonnelAuthorization(**data.dict())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    await session.refresh(
        obj,
        [
            "account_information",
            "authorization_scope_cessna",
            "authorization_scope_baron",
            "authorization_scope_others",
        ],
    )
    return PersonnelAuthorizationRead.from_orm(obj)


async def update_personnel_authorization(
    session: AsyncSession,
    auth_id: int,
    data: PersonnelAuthorizationUpdate,
) -> Optional[PersonnelAuthorizationRead]:
    result = await session.execute(
        select(PersonnelAuthorization)
        .options(
            selectinload(PersonnelAuthorization.account_information),
            selectinload(PersonnelAuthorization.authorization_scope_cessna),
            selectinload(PersonnelAuthorization.authorization_scope_baron),
            selectinload(PersonnelAuthorization.authorization_scope_others),
        )
        .where(PersonnelAuthorization.id == auth_id)
        .where(PersonnelAuthorization.is_deleted == False)
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
    await session.refresh(
        obj,
        [
            "account_information",
            "authorization_scope_cessna",
            "authorization_scope_baron",
            "authorization_scope_others",
        ],
    )
    return PersonnelAuthorizationRead.from_orm(obj)


async def soft_delete_personnel_authorization(
    session: AsyncSession,
    auth_id: int,
) -> bool:
    obj = await session.get(PersonnelAuthorization, auth_id)
    if not obj or obj.is_deleted:
        return False
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True
