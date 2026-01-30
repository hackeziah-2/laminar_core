from typing import Optional, List, Tuple

from fastapi import HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import AccountInformation
from app.schemas.account_schema import (
    AccountInformationCreate,
    AccountInformationUpdate,
    AccountInformationRead,
)
from app.core.security import get_password_hash


async def create_account_information(
    session: AsyncSession,
    data: AccountInformationCreate
) -> AccountInformationRead:
    """Create a new Account Information entry."""
    # Check for duplicate username (excluding soft-deleted)
    result = await session.execute(
        select(AccountInformation).where(
            AccountInformation.username == data.username,
            AccountInformation.is_deleted == False
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Account with this username already exists"
        )

    # Hash password before storing (get_password_hash handles truncation)
    account_data = data.dict(exclude={'password'})
    
    # Ensure status is a boolean (defaults to True if not provided)
    # Pydantic should already validate it, but we ensure it's a boolean
    if 'status' not in account_data or account_data['status'] is None:
        account_data['status'] = True
    elif not isinstance(account_data['status'], bool):
        # Convert string/number to boolean if needed
        account_data['status'] = bool(account_data['status'])
    
    account_data['password'] = get_password_hash(data.password)
    
    try:
        account = AccountInformation(**account_data)
        session.add(account)
        await session.commit()
        await session.refresh(account)
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Failed to create account: {str(e)}"
        )
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return AccountInformationRead.from_orm(account)


async def get_account_information(
    session: AsyncSession,
    id: int
) -> Optional[AccountInformationRead]:
    """Get an Account Information entry by ID."""
    result = await session.execute(
        select(AccountInformation)
        .where(AccountInformation.id == id)
        .where(AccountInformation.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    return AccountInformationRead.from_orm(obj)


async def update_account_information(
    session: AsyncSession,
    account_id: int,
    account_in: AccountInformationUpdate
) -> Optional[AccountInformationRead]:
    """Update an Account Information entry."""
    obj = await session.get(AccountInformation, account_id)
    if not obj or obj.is_deleted:
        return None

    update_data = account_in.dict(exclude_unset=True, exclude={'password'})
    
    # Check for duplicate username if username is being updated (excluding soft-deleted)
    if 'username' in update_data:
        result = await session.execute(
            select(AccountInformation).where(
                AccountInformation.username == update_data['username'],
                AccountInformation.id != account_id,
                AccountInformation.is_deleted == False
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Account with this username already exists"
            )
    
    # Hash password if provided (get_password_hash handles truncation)
    if account_in.password:
        update_data['password'] = get_password_hash(account_in.password)
    
    # Ensure status is a boolean if provided
    if 'status' in update_data and not isinstance(update_data['status'], bool):
        # Convert string/number to boolean if needed
        update_data['status'] = bool(update_data['status'])
    
    for k, v in update_data.items():
        setattr(obj, k, v)

    try:
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Failed to update account: {str(e)}"
        )

    return AccountInformationRead.from_orm(obj)


async def list_account_informations(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    sort: Optional[str] = "",
) -> Tuple[List[AccountInformation], int]:
    """List Account Information entries with pagination."""
    stmt = (
        select(AccountInformation)
        .where(AccountInformation.is_deleted == False)
    )

    # Search functionality
    if search:
        q = f"%{search}%"
        stmt = stmt.where(
            or_(
                AccountInformation.username.ilike(q),
                AccountInformation.first_name.ilike(q),
                AccountInformation.last_name.ilike(q),
                AccountInformation.middle_name.ilike(q),
                AccountInformation.designation.ilike(q),
                AccountInformation.license_no.ilike(q),
            )
        )

    # Whitelist sortable fields
    sortable_fields = {
        "id": AccountInformation.id,
        "username": AccountInformation.username,
        "first_name": AccountInformation.first_name,
        "last_name": AccountInformation.last_name,
        "status": AccountInformation.status,
        "created_at": AccountInformation.created_at,
        "updated_at": AccountInformation.updated_at,
    }

    # Multi-sort logic
    if sort:
        for field in sort.split(","):
            desc_order = field.startswith("-")
            field_name = field.lstrip("-")

            column = sortable_fields.get(field_name)
            if column is None:
                continue

            stmt = stmt.order_by(
                column.desc() if desc_order else column.asc()
            )
    else:
        # Default ordering
        stmt = stmt.order_by(AccountInformation.created_at.desc())

    # Total count query (same filters, no ORDER BY)
    count_stmt = (
        select(func.count())
        .select_from(AccountInformation)
        .where(AccountInformation.is_deleted == False)
    )

    if search:
        q = f"%{search}%"
        count_stmt = count_stmt.where(
            or_(
                AccountInformation.username.ilike(q),
                AccountInformation.first_name.ilike(q),
                AccountInformation.last_name.ilike(q),
                AccountInformation.middle_name.ilike(q),
                AccountInformation.designation.ilike(q),
                AccountInformation.license_no.ilike(q),
            )
        )

    total = (await session.execute(count_stmt)).scalar()

    # Pagination
    stmt = stmt.limit(limit).offset(offset)

    result = await session.execute(stmt)
    items = result.scalars().all()

    return items, total


async def get_all_account_informations_list(
    session: AsyncSession,
    designation: Optional[List[str]] = None,
    search: Optional[str] = None
) -> List[AccountInformation]:
    """Get all Account Information entries (for list endpoint - no pagination)."""
    stmt = (
        select(AccountInformation)
        .where(AccountInformation.is_deleted == False)
    )
    
    # Filter by designation(s) if provided - match ANY of the provided designations (OR logic)
    if designation:
        designation_filters = []
        for desig in designation:
            if desig:  # Skip empty strings
                designation_filters.append(AccountInformation.designation.ilike(f"%{desig}%"))
        
        if designation_filters:
            # Use OR to match any of the designations
            stmt = stmt.where(or_(*designation_filters))
    
    # Search functionality - search across name fields and license_no
    if search:
        q = f"%{search}%"
        stmt = stmt.where(
            or_(
                AccountInformation.first_name.ilike(q),
                AccountInformation.last_name.ilike(q),
                AccountInformation.middle_name.ilike(q),
                AccountInformation.license_no.ilike(q),
                AccountInformation.username.ilike(q),
            )
        )
    
    stmt = stmt.order_by(AccountInformation.last_name.asc(), AccountInformation.first_name.asc())
    
    result = await session.execute(stmt)
    items = result.scalars().all()
    
    return items


async def soft_delete_account_information(
    session: AsyncSession,
    account_id: int
) -> bool:
    """Soft delete an Account Information entry."""
    obj = await session.get(AccountInformation, account_id)
    if not obj or obj.is_deleted:
        return False

    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True
