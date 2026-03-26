import os
import uuid
from typing import Optional, List, Tuple

from fastapi import HTTPException, UploadFile
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.upload_config import UPLOAD_DIR, ensure_uploads_dir
from app.models.aircraft_statutory_certificate import (
    AircraftStatutoryCertificate,
    CategoryTypeEnum,
)
from app.schemas.aircraft_statutory_certificate_schema import (
    AircraftStatutoryCertificateCreate,
    AircraftStatutoryCertificateUpdate,
    AircraftStatutoryCertificateRead,
)

UPLOAD_SUBDIR = "statutory_certificates"


def _sanitize_filename(name: str) -> str:
    if not name or not isinstance(name, str):
        return "upload"
    base = (name.split("/")[-1].split("\\")[-1] or "upload").strip()
    if not base or ".." in base:
        return "upload"
    return "".join(c for c in base if c.isalnum() or c in "._- ") or "upload"


async def _save_certificate_upload(upload_file: Optional[UploadFile]) -> Optional[str]:
    """Save uploaded file to uploads/statutory_certificates/; return relative path or None."""
    if not upload_file or not getattr(upload_file, "filename", None) or not getattr(upload_file, "read", None):
        return None
    ensure_uploads_dir()
    target_dir = UPLOAD_DIR / UPLOAD_SUBDIR
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_base = _sanitize_filename(upload_file.filename)
    unique_name = f"{uuid.uuid4().hex}_{safe_base}"
    path = target_dir / unique_name
    content = await upload_file.read()
    path.write_bytes(content)
    return f"{UPLOAD_SUBDIR}/{unique_name}"


async def list_aircraft_statutory_certificates(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    aircraft_fk: Optional[int] = None,
    category_type: Optional[CategoryTypeEnum] = None,
    sort: Optional[str] = "",
) -> Tuple[List[AircraftStatutoryCertificate], int]:
    """List certificates with pagination and optional filter by category_type and aircraft_fk."""
    stmt = (
        select(AircraftStatutoryCertificate)
        .options(selectinload(AircraftStatutoryCertificate.aircraft))
        .where(AircraftStatutoryCertificate.is_deleted == False)
    )
    if aircraft_fk is not None:
        stmt = stmt.where(AircraftStatutoryCertificate.aircraft_fk == aircraft_fk)
    if category_type is not None:
        stmt = stmt.where(AircraftStatutoryCertificate.category_type == category_type)

    sortable = {
        "id": AircraftStatutoryCertificate.id,
        "aircraft_fk": AircraftStatutoryCertificate.aircraft_fk,
        "category_type": AircraftStatutoryCertificate.category_type,
        "date_of_expiration": AircraftStatutoryCertificate.date_of_expiration,
        "created_at": AircraftStatutoryCertificate.created_at,
        "updated_at": AircraftStatutoryCertificate.updated_at,
    }
    if sort:
        for part in sort.split(","):
            desc = part.startswith("-")
            name = part.lstrip("-")
            col = sortable.get(name)
            if col is not None:
                stmt = stmt.order_by(col.desc() if desc else col.asc())
    else:
        stmt = stmt.order_by(AircraftStatutoryCertificate.created_at.desc())

    count_stmt = (
        select(func.count())
        .select_from(AircraftStatutoryCertificate)
        .where(AircraftStatutoryCertificate.is_deleted == False)
    )
    if aircraft_fk is not None:
        count_stmt = count_stmt.where(AircraftStatutoryCertificate.aircraft_fk == aircraft_fk)
    if category_type is not None:
        count_stmt = count_stmt.where(AircraftStatutoryCertificate.category_type == category_type)

    total = (await session.execute(count_stmt)).scalar()
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


async def get_aircraft_statutory_certificate(
    session: AsyncSession, cert_id: int
) -> Optional[AircraftStatutoryCertificate]:
    """Get a single certificate by ID."""
    result = await session.execute(
        select(AircraftStatutoryCertificate)
        .options(selectinload(AircraftStatutoryCertificate.aircraft))
        .where(AircraftStatutoryCertificate.id == cert_id)
        .where(AircraftStatutoryCertificate.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_aircraft_statutory_certificate_by_aircraft(
    session: AsyncSession, cert_id: int, aircraft_fk: int
) -> Optional[AircraftStatutoryCertificate]:
    """Get a single certificate by ID scoped to aircraft."""
    result = await session.execute(
        select(AircraftStatutoryCertificate)
        .options(selectinload(AircraftStatutoryCertificate.aircraft))
        .where(AircraftStatutoryCertificate.id == cert_id)
        .where(AircraftStatutoryCertificate.aircraft_fk == aircraft_fk)
        .where(AircraftStatutoryCertificate.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def create_aircraft_statutory_certificate(
    session: AsyncSession,
    data: AircraftStatutoryCertificateCreate,
    upload_file: Optional[UploadFile] = None,
) -> AircraftStatutoryCertificateRead:
    """Create a new certificate with optional file upload."""
    cert_data = data.dict()
    duplicate_stmt = (
        select(AircraftStatutoryCertificate)
        .where(AircraftStatutoryCertificate.aircraft_fk == data.aircraft_fk)
        .where(AircraftStatutoryCertificate.category_type == data.category_type)
        .where(AircraftStatutoryCertificate.is_deleted == False)
    )
    if data.date_of_expiration is None:
        duplicate_stmt = duplicate_stmt.where(AircraftStatutoryCertificate.date_of_expiration.is_(None))
    else:
        duplicate_stmt = duplicate_stmt.where(
            AircraftStatutoryCertificate.date_of_expiration == data.date_of_expiration
        )
    duplicate_result = await session.execute(duplicate_stmt.limit(1))
    if duplicate_result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Entry already Exists")

    file_path = await _save_certificate_upload(upload_file)
    if file_path:
        cert_data["file_path"] = file_path
    try:
        obj = AircraftStatutoryCertificate(**cert_data)
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
        await session.refresh(obj, ["aircraft"])
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create certificate: {str(e)}")
    return AircraftStatutoryCertificateRead.from_orm(obj)


async def update_aircraft_statutory_certificate(
    session: AsyncSession,
    cert_id: int,
    data: AircraftStatutoryCertificateUpdate,
    upload_file: Optional[UploadFile] = None,
) -> Optional[AircraftStatutoryCertificateRead]:
    """Update a certificate; optional file upload replaces file_path."""
    result = await session.execute(
        select(AircraftStatutoryCertificate)
        .options(selectinload(AircraftStatutoryCertificate.aircraft))
        .where(AircraftStatutoryCertificate.id == cert_id)
        .where(AircraftStatutoryCertificate.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    update_data = data.dict(exclude_unset=True)
    file_path = await _save_certificate_upload(upload_file)
    if file_path:
        update_data["file_path"] = file_path
    for k, v in update_data.items():
        setattr(obj, k, v)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    await session.refresh(obj, ["aircraft"])
    return AircraftStatutoryCertificateRead.from_orm(obj)


async def soft_delete_aircraft_statutory_certificate(
    session: AsyncSession, cert_id: int
) -> bool:
    """Soft delete a certificate."""
    obj = await session.get(AircraftStatutoryCertificate, cert_id)
    if not obj or obj.is_deleted:
        return False
    obj.soft_delete()
    session.add(obj)
    await session.commit()
    return True
