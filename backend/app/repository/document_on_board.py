import os
from datetime import date, datetime
from typing import Optional, List, Tuple

from sqlalchemy import select, or_, cast, String, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, UploadFile

from app.core.upload_path import UPLOAD_DIR
from app.models.aircraft import Aircraft
from app.models.document_on_board import DocumentOnBoard, DocumentStatusEnum
from app.schemas.document_on_board_schema import (
    DocumentOnBoardCreate,
    DocumentOnBoardUpdate,
    DocumentOnBoardRead,
)


async def get_document_on_board(
    session: AsyncSession, document_id: int
) -> Optional[DocumentOnBoardRead]:
    """Get a single DocumentOnBoard by ID."""
    result = await session.execute(
        select(DocumentOnBoard)
        .options(selectinload(DocumentOnBoard.aircraft))
        .where(DocumentOnBoard.document_id == document_id)
        .where(DocumentOnBoard.is_deleted == False)
    )
    document = result.scalar_one_or_none()
    if not document:
        return None
    return DocumentOnBoardRead.from_orm(document)


async def get_document_on_board_by_aircraft(
    session: AsyncSession, document_id: int, aircraft_id: int
) -> Optional[DocumentOnBoardRead]:
    """Get a single DocumentOnBoard by ID, scoped to aircraft_id."""
    result = await session.execute(
        select(DocumentOnBoard)
        .options(selectinload(DocumentOnBoard.aircraft))
        .where(DocumentOnBoard.document_id == document_id)
        .where(DocumentOnBoard.aircraft_id == aircraft_id)
        .where(DocumentOnBoard.is_deleted == False)
    )
    document = result.scalar_one_or_none()
    if not document:
        return None
    return DocumentOnBoardRead.from_orm(document)


async def list_documents_on_board(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    aircraft_id: Optional[int] = None,
    status: Optional[str] = None,
    sort: Optional[str] = "",
) -> Tuple[List[DocumentOnBoard], int]:
    """List DocumentOnBoard entries with pagination, search, and filtering."""
    stmt = (
        select(DocumentOnBoard)
        .options(selectinload(DocumentOnBoard.aircraft))
        .where(DocumentOnBoard.is_deleted == False)
    )

    # Search (strip whitespace; treat empty as no search): document_name, description, aircraft registration
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.join(Aircraft, DocumentOnBoard.aircraft_id == Aircraft.id).where(
            or_(
                DocumentOnBoard.document_name.ilike(q),
                func.coalesce(cast(DocumentOnBoard.description, String), "").ilike(q),
                Aircraft.registration.ilike(q),
            )
        )

    # Aircraft filter
    if aircraft_id:
        stmt = stmt.where(DocumentOnBoard.aircraft_id == aircraft_id)

    # Status filter
    if status and status.lower() != "all":
        stmt = stmt.where(
            func.lower(cast(DocumentOnBoard.status, String)) == status.lower()
        )

    # Whitelist sortable fields
    sortable_fields = {
        "document_name": DocumentOnBoard.document_name,
        "issue_date": DocumentOnBoard.issue_date,
        "expiry_date": DocumentOnBoard.expiry_date,
        "status": DocumentOnBoard.status,
        "created_at": DocumentOnBoard.created_at,
        "updated_at": DocumentOnBoard.updated_at,
    }

    # Multi-sort logic
    if sort:
        for field in sort.split(","):
            desc_order = field.startswith("-")
            field_name = field.lstrip("-")

            column = sortable_fields.get(field_name)
            if column is None:
                continue  # ignore invalid fields safely

            stmt = stmt.order_by(column.desc() if desc_order else column.asc())
    else:
        stmt = stmt.order_by(DocumentOnBoard.created_at.desc())

    # Total count (same filters, no ORDER BY)
    count_stmt = (
        select(func.count())
        .select_from(DocumentOnBoard)
        .where(DocumentOnBoard.is_deleted == False)
    )

    if search and search.strip():
        q = f"%{search.strip()}%"
        count_stmt = count_stmt.join(Aircraft, DocumentOnBoard.aircraft_id == Aircraft.id).where(
            or_(
                DocumentOnBoard.document_name.ilike(q),
                func.coalesce(cast(DocumentOnBoard.description, String), "").ilike(q),
                Aircraft.registration.ilike(q),
            )
        )

    if aircraft_id:
        count_stmt = count_stmt.where(DocumentOnBoard.aircraft_id == aircraft_id)

    if status and status.lower() != "all":
        count_stmt = count_stmt.where(
            func.lower(cast(DocumentOnBoard.status, String)) == status.lower()
        )

    total_count = (await session.execute(count_stmt)).scalar()

    # Pagination
    stmt = stmt.limit(limit).offset(offset)

    result = await session.execute(stmt)
    items = result.scalars().all()

    return items, total_count


async def create_document_on_board(
    session: AsyncSession,
    data: DocumentOnBoardCreate,
    upload_file: UploadFile = None,
) -> DocumentOnBoardRead:
    """Create a new DocumentOnBoard entry."""
    document_data = data.dict()

    # Convert status string to DB enum value (case-insensitive). PostgreSQL expects "Active", "Expired", etc.
    if "status" in document_data and document_data["status"]:
        try:
            status_str = str(document_data["status"]).strip().lower()
            status_mapping = {
                "active": DocumentStatusEnum.ACTIVE.value,  # "Active"
                "expired": DocumentStatusEnum.EXPIRED.value,
                "expiring soon": DocumentStatusEnum.EXPIRING_SOON.value,
                "inactive": DocumentStatusEnum.INACTIVE.value,
            }
            document_data["status"] = status_mapping.get(status_str, DocumentStatusEnum.ACTIVE.value)
        except (KeyError, ValueError, AttributeError):
            document_data["status"] = DocumentStatusEnum.ACTIVE.value
    else:
        document_data.pop("status", None)

    # Handle file upload (absolute path for write; store relative for DB/download)
    if upload_file and upload_file.filename:
        file_path = UPLOAD_DIR / upload_file.filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(await upload_file.read())
        document_data["file_path"] = f"uploads/{upload_file.filename}"

    try:
        document = DocumentOnBoard(**document_data)
        session.add(document)
        await session.commit()
        await session.refresh(document)
        await session.refresh(document, ["aircraft"])
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=400, detail=f"Failed to create document: {str(e)}"
        )
    return DocumentOnBoardRead.from_orm(document)


async def update_document_on_board(
    session: AsyncSession,
    document_id: int,
    document_in: DocumentOnBoardUpdate,
    upload_file: UploadFile = None,
) -> Optional[DocumentOnBoardRead]:
    """Update a DocumentOnBoard entry."""
    result = await session.execute(
        select(DocumentOnBoard)
        .options(selectinload(DocumentOnBoard.aircraft))
        .where(DocumentOnBoard.document_id == document_id)
        .where(DocumentOnBoard.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None

    update_data = document_in.dict(exclude_unset=True)

    # Convert status string to DB enum value (case-insensitive). PostgreSQL expects "Active", "Expired", etc.
    if "status" in update_data and update_data["status"]:
        try:
            status_str = str(update_data["status"]).strip().lower()
            status_mapping = {
                "active": DocumentStatusEnum.ACTIVE.value,
                "expired": DocumentStatusEnum.EXPIRED.value,
                "expiring soon": DocumentStatusEnum.EXPIRING_SOON.value,
                "inactive": DocumentStatusEnum.INACTIVE.value,
            }
            update_data["status"] = status_mapping.get(status_str, DocumentStatusEnum.ACTIVE.value)
        except (KeyError, ValueError, AttributeError):
            update_data["status"] = DocumentStatusEnum.ACTIVE.value

    # Handle file upload (absolute path for write; store relative for DB/download)
    if upload_file and upload_file.filename:
        file_path = UPLOAD_DIR / upload_file.filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(await upload_file.read())
        update_data["file_path"] = f"uploads/{upload_file.filename}"

    for k, v in update_data.items():
        setattr(obj, k, v)

    try:
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
        await session.refresh(obj, ["aircraft"])
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=400, detail=f"Failed to update document: {str(e)}"
        )
    return DocumentOnBoardRead.from_orm(obj)


async def soft_delete_document_on_board(
    session: AsyncSession, document_id: int
) -> bool:
    """Soft delete a DocumentOnBoard entry."""
    result = await session.execute(
        select(DocumentOnBoard)
        .where(DocumentOnBoard.document_id == document_id)
        .where(DocumentOnBoard.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return False
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True


async def soft_delete_document_on_board_by_aircraft(
    session: AsyncSession, document_id: int, aircraft_id: int
) -> bool:
    """Soft delete a DocumentOnBoard entry, scoped to aircraft_id."""
    result = await session.execute(
        select(DocumentOnBoard)
        .where(DocumentOnBoard.document_id == document_id)
        .where(DocumentOnBoard.aircraft_id == aircraft_id)
        .where(DocumentOnBoard.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return False
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True
