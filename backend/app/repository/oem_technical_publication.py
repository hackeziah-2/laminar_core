from typing import Optional, List, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.oem_technical_publication import (
    OemTechnicalPublication,
    OemTechnicalPublicationCategoryTypeEnum,
)
from app.models.oem_item_type import OemItemType
from app.schemas.oem_technical_publication_schema import (
    OemTechnicalPublicationCreate,
    OemTechnicalPublicationUpdate,
    OemTechnicalPublicationRead,
)


def _category_type_from_str(value: Optional[str]) -> Optional[OemTechnicalPublicationCategoryTypeEnum]:
    """Convert string to OemTechnicalPublicationCategoryTypeEnum; return None if invalid or None."""
    if not value or not value.strip():
        return None
    v = value.strip()
    for e in OemTechnicalPublicationCategoryTypeEnum:
        if e.value == v or e.name == v:
            return e
    return None


async def list_oem_technical_publications(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    item_fk: Optional[int] = None,
    category_type: Optional[str] = None,
    search: Optional[str] = None,
    sort: str = "",
) -> Tuple[List[OemTechnicalPublication], int]:
    """List with pagination; filter by item_fk, category_type; search on item type name; sort by date_of_expiration (ASC/DESC)."""
    stmt = (
        select(OemTechnicalPublication)
        .options(selectinload(OemTechnicalPublication.item))
        .where(OemTechnicalPublication.is_deleted == False)
    )
    if item_fk is not None:
        stmt = stmt.where(OemTechnicalPublication.item_fk == item_fk)
    cat_enum = _category_type_from_str(category_type)
    if cat_enum is not None:
        stmt = stmt.where(OemTechnicalPublication.category_type == cat_enum)
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.outerjoin(OemTechnicalPublication.item)
        stmt = stmt.where(OemItemType.name.ilike(q))

    sortable = {
        "id": OemTechnicalPublication.id,
        "item_fk": OemTechnicalPublication.item_fk,
        "category_type": OemTechnicalPublication.category_type,
        "date_of_expiration": OemTechnicalPublication.date_of_expiration,
        "web_link": OemTechnicalPublication.web_link,
        "created_at": OemTechnicalPublication.created_at,
        "updated_at": OemTechnicalPublication.updated_at,
    }
    if sort:
        order_parts = []
        for part in sort.split(","):
            desc = part.startswith("-")
            name = part.lstrip("-").strip()
            col = sortable.get(name)
            if col is not None:
                if desc:
                    order_parts.append(col.desc().nullslast())
                else:
                    order_parts.append(col.asc().nullsfirst())
        if order_parts:
            stmt = stmt.order_by(*order_parts)
    else:
        stmt = stmt.order_by(OemTechnicalPublication.date_of_expiration.desc().nullslast())

    count_stmt = (
        select(func.count())
        .select_from(OemTechnicalPublication)
        .where(OemTechnicalPublication.is_deleted == False)
    )
    if item_fk is not None:
        count_stmt = count_stmt.where(OemTechnicalPublication.item_fk == item_fk)
    if cat_enum is not None:
        count_stmt = count_stmt.where(OemTechnicalPublication.category_type == cat_enum)
    if search and search.strip():
        q = f"%{search.strip()}%"
        count_stmt = count_stmt.outerjoin(
            OemTechnicalPublication.item
        ).where(OemItemType.name.ilike(q))
    total = (await session.execute(count_stmt)).scalar()
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


async def get_oem_technical_publication(
    session: AsyncSession,
    publication_id: int,
) -> Optional[OemTechnicalPublication]:
    """Get one by ID."""
    result = await session.execute(
        select(OemTechnicalPublication)
        .options(selectinload(OemTechnicalPublication.item))
        .where(OemTechnicalPublication.id == publication_id)
        .where(OemTechnicalPublication.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def create_oem_technical_publication(
    session: AsyncSession,
    data: OemTechnicalPublicationCreate,
) -> OemTechnicalPublicationRead:
    """Create."""
    payload = data.dict()
    raw_cat = payload.get("category_type")
    if isinstance(raw_cat, str):
        payload["category_type"] = _category_type_from_str(raw_cat) or getattr(
            data, "category_type"
        )
    elif hasattr(raw_cat, "value"):
        payload["category_type"] = raw_cat
    obj = OemTechnicalPublication(**payload)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    await session.refresh(obj, ["item"])
    return OemTechnicalPublicationRead.from_orm(obj)


async def update_oem_technical_publication(
    session: AsyncSession,
    publication_id: int,
    data: OemTechnicalPublicationUpdate,
) -> Optional[OemTechnicalPublicationRead]:
    """Update."""
    result = await session.execute(
        select(OemTechnicalPublication)
        .options(selectinload(OemTechnicalPublication.item))
        .where(OemTechnicalPublication.id == publication_id)
        .where(OemTechnicalPublication.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    update_data = data.dict(exclude_unset=True)
    if "category_type" in update_data and isinstance(update_data["category_type"], str):
        cat_enum = _category_type_from_str(update_data["category_type"])
        if cat_enum is not None:
            update_data["category_type"] = cat_enum
    for k, v in update_data.items():
        setattr(obj, k, v)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    await session.refresh(obj, ["item"])
    return OemTechnicalPublicationRead.from_orm(obj)


async def soft_delete_oem_technical_publication(
    session: AsyncSession,
    publication_id: int,
) -> bool:
    """Soft delete."""
    obj = await session.get(OemTechnicalPublication, publication_id)
    if not obj or obj.is_deleted:
        return False
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True
