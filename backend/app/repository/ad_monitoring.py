import os
from typing import Optional, List, Tuple

from fastapi import HTTPException, Request, UploadFile
from sqlalchemy import select, func, or_, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only, noload, selectinload

from app.database import set_audit_fields
from app.upload_config import UPLOAD_DIR, ensure_uploads_dir
from app.models.account import AccountInformation
from app.models.ad_monitoring import ADMonitoring, WorkOrderADMonitoring
from app.models.aircraft import Aircraft
from app.models.audit_log import AuditAction
from app.services.audit_trail_service import create_audit_log, serialize_audit_data

ensure_uploads_dir()
from app.schemas.ad_monitoring_schema import (
    ADMonitoringCreate,
    ADMonitoringUpdate,
    ADMonitoringRead,
    WorkOrderADMonitoringCreate,
    WorkOrderADMonitoringUpdate,
    WorkOrderADMonitoringRead,
)


# ---------- ADMonitoring ----------
async def get_ad_monitoring(
    session: AsyncSession, ad_id: int
) -> Optional[ADMonitoringRead]:
    """Get a single ADMonitoring by ID."""
    result = await session.execute(
        select(ADMonitoring)
        .options(
            selectinload(ADMonitoring.aircraft),
            selectinload(ADMonitoring.ad_works),
        )
        .where(ADMonitoring.id == ad_id)
        .where(ADMonitoring.is_deleted == False)
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    return ADMonitoringRead.from_orm(row)


async def get_ad_monitoring_by_aircraft(
    session: AsyncSession, ad_id: int, aircraft_id: int
) -> Optional[ADMonitoringRead]:
    """Get a single ADMonitoring by ID, scoped to aircraft_id."""
    result = await session.execute(
        select(ADMonitoring)
        .options(
            selectinload(ADMonitoring.aircraft),
            selectinload(ADMonitoring.ad_works),
        )
        .where(ADMonitoring.id == ad_id)
        .where(ADMonitoring.aircraft_fk == aircraft_id)
        .where(ADMonitoring.is_deleted == False)
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    return ADMonitoringRead.from_orm(row)


def _ad_monitoring_filters(
    aircraft_fk: Optional[int] = None,
    search: Optional[str] = None,
    compli_date: Optional[str] = None,
    inspection_interval: Optional[str] = None,
):
    """Shared WHERE clauses for list + COUNT (search/filter preserved)."""
    filters = [ADMonitoring.is_deleted.is_(False)]
    if aircraft_fk is not None:
        filters.append(ADMonitoring.aircraft_fk == aircraft_fk)
    if inspection_interval and inspection_interval.strip():
        filters.append(
            ADMonitoring.inspection_interval.ilike(
                f"%{inspection_interval.strip()}%"
            )
        )
    if compli_date and compli_date.strip():
        filters.append(
            cast(ADMonitoring.compli_date, String).ilike(
                f"%{compli_date.strip()}%"
            )
        )
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                ADMonitoring.ad_number.ilike(pattern),
                ADMonitoring.subject.ilike(pattern),
                ADMonitoring.inspection_interval.ilike(pattern),
                cast(ADMonitoring.compli_date, String).ilike(pattern),
            )
        )
    return filters


def _ad_monitoring_list_options():
    """Load only response columns/relations; avoid audit N+1 and wide aircraft rows."""
    return (
        load_only(
            ADMonitoring.id,
            ADMonitoring.aircraft_fk,
            ADMonitoring.ad_number,
            ADMonitoring.subject,
            ADMonitoring.inspection_interval,
            ADMonitoring.compli_date,
            ADMonitoring.file_path,
            ADMonitoring.web_link,
            ADMonitoring.created_at,
            ADMonitoring.updated_at,
        ),
        selectinload(ADMonitoring.aircraft).load_only(
            Aircraft.id,
            Aircraft.registration,
        ),
        selectinload(ADMonitoring.ad_works).load_only(
            WorkOrderADMonitoring.id,
            WorkOrderADMonitoring.ad_monitoring_fk,
            WorkOrderADMonitoring.work_order_number,
            WorkOrderADMonitoring.atl_ref,
            WorkOrderADMonitoring.last_done_date,
            WorkOrderADMonitoring.last_done_tach,
            WorkOrderADMonitoring.next_due_aftt,
            WorkOrderADMonitoring.next_due_tach,
        ),
        noload(ADMonitoring.created_by_user),
        noload(ADMonitoring.updated_by_user),
    )


async def list_ad_monitoring(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    aircraft_fk: Optional[int] = None,
    search: Optional[str] = None,
    compli_date: Optional[str] = None,
    inspection_interval: Optional[str] = None,
    sort: Optional[str] = "",
) -> Tuple[List[ADMonitoring], int]:
    """List ADMonitoring with pagination and filtering.

    Filters:
    - search: case-insensitive partial match across ad_number, subject,
      inspection_interval, and compli_date.
    - compli_date: case-insensitive partial match on compli_date (cast to text,
      e.g. "2024", "2024-01", "2024-01-15").
    - inspection_interval: case-insensitive partial match on inspection_interval.

    Pagination is applied in the database (LIMIT/OFFSET). Total uses a separate
    COUNT query on the same filters, without loading rows or related collections.
    """
    filters = _ad_monitoring_filters(
        aircraft_fk=aircraft_fk,
        search=search,
        compli_date=compli_date,
        inspection_interval=inspection_interval,
    )

    count_stmt = select(func.count(ADMonitoring.id)).where(*filters)
    total = int((await session.execute(count_stmt)).scalar() or 0)

    stmt = (
        select(ADMonitoring)
        .options(*_ad_monitoring_list_options())
        .where(*filters)
    )

    sortable = {
        "id": ADMonitoring.id,
        "aircraft_fk": ADMonitoring.aircraft_fk,
        "ad_number": ADMonitoring.ad_number,
        "subject": ADMonitoring.subject,
        "inspection_interval": ADMonitoring.inspection_interval,
        "compli_date": ADMonitoring.compli_date,
        "created_at": ADMonitoring.created_at,
        "updated_at": ADMonitoring.updated_at,
    }
    if sort:
        for part in sort.split(","):
            desc = part.startswith("-")
            name = part.lstrip("-")
            col = sortable.get(name)
            if col is not None:
                stmt = stmt.order_by(col.desc() if desc else col.asc())
    else:
        stmt = stmt.order_by(ADMonitoring.created_at.desc())

    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


async def create_ad_monitoring(
    session: AsyncSession,
    data: ADMonitoringCreate,
    upload_file: UploadFile = None,
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> ADMonitoringRead:
    """Create ADMonitoring with optional file upload."""
    ad_data = data.dict()
    if upload_file and getattr(upload_file, "filename", None):
        file_path = os.path.join(str(UPLOAD_DIR), upload_file.filename)
        with open(file_path, "wb") as f:
            f.write(await upload_file.read())
        ad_data["file_path"] = file_path
    obj = ADMonitoring(**ad_data)
    try:
        session.add(obj)
        if audit_account_id is not None:
            await set_audit_fields(obj, audit_account_id, is_create=True)
        await session.commit()
        await session.refresh(obj)
        await session.refresh(obj, ["aircraft", "ad_works"])
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create AD monitoring: {str(e)}")

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

    return ADMonitoringRead.from_orm(obj)


async def update_ad_monitoring(
    session: AsyncSession,
    ad_id: int,
    data: ADMonitoringUpdate,
    upload_file: UploadFile = None,
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> Optional[ADMonitoringRead]:
    """Update ADMonitoring with optional file upload."""
    result = await session.execute(
        select(ADMonitoring)
        .options(
            selectinload(ADMonitoring.aircraft),
            selectinload(ADMonitoring.ad_works),
        )
        .where(ADMonitoring.id == ad_id)
        .where(ADMonitoring.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    old_data_snapshot = serialize_audit_data(obj)
    update_data = data.dict(exclude_unset=True)
    if upload_file and getattr(upload_file, "filename", None):
        file_path = os.path.join(str(UPLOAD_DIR), upload_file.filename)
        with open(file_path, "wb") as f:
            f.write(await upload_file.read())
        update_data["file_path"] = file_path
    for k, v in update_data.items():
        setattr(obj, k, v)
    try:
        session.add(obj)
        if audit_account_id is not None:
            await set_audit_fields(obj, audit_account_id, is_create=False)
        await session.commit()
        await session.refresh(obj)
        await session.refresh(obj, ["aircraft", "ad_works"])
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to update AD monitoring: {str(e)}")

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

    return ADMonitoringRead.from_orm(obj)


async def soft_delete_ad_monitoring(
    session: AsyncSession,
    ad_id: int,
    *,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> bool:
    """Soft delete ADMonitoring."""
    result = await session.execute(
        select(ADMonitoring)
        .where(ADMonitoring.id == ad_id)
        .where(ADMonitoring.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
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
            record_id=ad_id,
            action=AuditAction.DELETE,
            old_data=old_data_snapshot,
            new_data=None,
            current_user=audit_user,
            request=audit_request,
        )

    return True


async def soft_delete_ad_monitoring_by_aircraft(
    session: AsyncSession,
    ad_id: int,
    aircraft_id: int,
    *,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> bool:
    """Soft delete ADMonitoring scoped to aircraft_id."""
    result = await session.execute(
        select(ADMonitoring)
        .where(ADMonitoring.id == ad_id)
        .where(ADMonitoring.aircraft_fk == aircraft_id)
        .where(ADMonitoring.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
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
            record_id=ad_id,
            action=AuditAction.DELETE,
            old_data=old_data_snapshot,
            new_data=None,
            current_user=audit_user,
            request=audit_request,
        )

    return True


# ---------- WorkOrderADMonitoring ----------
def _work_order_list_options():
    """Load parent AD summary only; skip unused relations to avoid N+1."""
    return (
        load_only(
            WorkOrderADMonitoring.id,
            WorkOrderADMonitoring.ad_monitoring_fk,
            WorkOrderADMonitoring.work_order_number,
            WorkOrderADMonitoring.last_done_aftt,
            WorkOrderADMonitoring.last_done_tach,
            WorkOrderADMonitoring.last_done_date,
            WorkOrderADMonitoring.next_due_aftt,
            WorkOrderADMonitoring.next_due_tach,
            WorkOrderADMonitoring.atl_ref,
            WorkOrderADMonitoring.created_at,
            WorkOrderADMonitoring.updated_at,
        ),
        selectinload(WorkOrderADMonitoring.ad_monitoring).options(
            load_only(
                ADMonitoring.id,
                ADMonitoring.ad_number,
                ADMonitoring.subject,
            ),
            noload(ADMonitoring.ad_works),
            noload(ADMonitoring.aircraft),
            noload(ADMonitoring.created_by_user),
            noload(ADMonitoring.updated_by_user),
        ),
        noload(WorkOrderADMonitoring.created_by_user),
        noload(WorkOrderADMonitoring.updated_by_user),
    )


def _work_order_select():
    """Base select for WorkOrderADMonitoring with ad_monitoring loaded."""
    return select(WorkOrderADMonitoring).options(*_work_order_list_options())


def _work_order_filters(ad_monitoring_fk: Optional[int] = None):
    filters = [WorkOrderADMonitoring.is_deleted.is_(False)]
    if ad_monitoring_fk is not None:
        filters.append(WorkOrderADMonitoring.ad_monitoring_fk == ad_monitoring_fk)
    return filters


async def get_work_order_ad_monitoring(
    session: AsyncSession, work_order_id: int
) -> Optional[WorkOrderADMonitoringRead]:
    """Get a single WorkOrderADMonitoring by ID."""
    result = await session.execute(
        _work_order_select()
        .where(WorkOrderADMonitoring.id == work_order_id)
        .where(WorkOrderADMonitoring.is_deleted == False)
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    return WorkOrderADMonitoringRead.from_orm(row)


async def get_work_order_ad_monitoring_by_ad(
    session: AsyncSession, work_order_id: int, ad_monitoring_id: int
) -> Optional[WorkOrderADMonitoringRead]:
    """Get WorkOrderADMonitoring by ID scoped to ad_monitoring_id."""
    result = await session.execute(
        _work_order_select()
        .where(WorkOrderADMonitoring.id == work_order_id)
        .where(WorkOrderADMonitoring.ad_monitoring_fk == ad_monitoring_id)
        .where(WorkOrderADMonitoring.is_deleted == False)
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    return WorkOrderADMonitoringRead.from_orm(row)


async def list_work_order_ad_monitoring(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    ad_monitoring_fk: Optional[int] = None,
    sort: Optional[str] = "",
) -> Tuple[List[WorkOrderADMonitoring], int]:
    """List WorkOrderADMonitoring with optional filter by ad_monitoring_fk.

    Pagination is applied in the database (LIMIT/OFFSET). Total uses a separate
    COUNT query on the same filters.
    """
    filters = _work_order_filters(ad_monitoring_fk=ad_monitoring_fk)

    count_stmt = select(func.count(WorkOrderADMonitoring.id)).where(*filters)
    total = int((await session.execute(count_stmt)).scalar() or 0)

    stmt = select(WorkOrderADMonitoring).options(*_work_order_list_options()).where(
        *filters
    )

    sortable = {
        "id": WorkOrderADMonitoring.id,
        "ad_monitoring_fk": WorkOrderADMonitoring.ad_monitoring_fk,
        "work_order_number": WorkOrderADMonitoring.work_order_number,
        "last_done_aftt": WorkOrderADMonitoring.last_done_aftt,
        "last_done_tach": WorkOrderADMonitoring.last_done_tach,
        "last_done_date": WorkOrderADMonitoring.last_done_date,
        "next_due_aftt": WorkOrderADMonitoring.next_due_aftt,
        "next_due_tach": WorkOrderADMonitoring.next_due_tach,
        "atl_ref": WorkOrderADMonitoring.atl_ref,
        "created_at": WorkOrderADMonitoring.created_at,
        "updated_at": WorkOrderADMonitoring.updated_at,
    }
    if sort:
        for part in sort.split(","):
            desc = part.startswith("-")
            name = part.lstrip("-")
            col = sortable.get(name)
            if col is not None:
                stmt = stmt.order_by(col.desc() if desc else col.asc())
    else:
        stmt = stmt.order_by(WorkOrderADMonitoring.created_at.desc())

    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


async def create_work_order_ad_monitoring(
    session: AsyncSession,
    data: WorkOrderADMonitoringCreate,
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> WorkOrderADMonitoringRead:
    """Create WorkOrderADMonitoring."""
    obj = WorkOrderADMonitoring(**data.dict())
    session.add(obj)
    if audit_account_id is not None:
        await set_audit_fields(obj, audit_account_id, is_create=True)
    await session.commit()
    # Re-fetch with relationship loaded to avoid lazy load in from_orm (async session)
    result = await session.execute(
        _work_order_select()
        .where(WorkOrderADMonitoring.id == obj.id)
        .where(WorkOrderADMonitoring.is_deleted == False)
    )
    row = result.scalar_one_or_none()
    assert row is not None, "Work order just created"

    if audit_module_name and audit_table_name:
        await create_audit_log(
            db=session,
            module_name=audit_module_name,
            table_name=audit_table_name,
            record_id=row.id,
            action=AuditAction.CREATE,
            old_data=None,
            new_data=row,
            current_user=audit_user,
            request=audit_request,
        )

    return WorkOrderADMonitoringRead.from_orm(row)


async def update_work_order_ad_monitoring(
    session: AsyncSession,
    work_order_id: int,
    data: WorkOrderADMonitoringUpdate,
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> Optional[WorkOrderADMonitoringRead]:
    """Update WorkOrderADMonitoring by ID."""
    result = await session.execute(
        _work_order_select()
        .where(WorkOrderADMonitoring.id == work_order_id)
        .where(WorkOrderADMonitoring.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    old_data_snapshot = serialize_audit_data(obj)
    for k, v in data.dict(exclude_unset=True).items():
        setattr(obj, k, v)
    session.add(obj)
    if audit_account_id is not None:
        await set_audit_fields(obj, audit_account_id, is_create=False)
    await session.commit()
    # Re-fetch with relationship loaded to avoid lazy load in from_orm (async session)
    result = await session.execute(
        _work_order_select()
        .where(WorkOrderADMonitoring.id == work_order_id)
        .where(WorkOrderADMonitoring.is_deleted == False)
    )
    row = result.scalar_one_or_none()

    if row and audit_module_name and audit_table_name:
        await create_audit_log(
            db=session,
            module_name=audit_module_name,
            table_name=audit_table_name,
            record_id=row.id,
            action=AuditAction.UPDATE,
            old_data=old_data_snapshot,
            new_data=row,
            current_user=audit_user,
            request=audit_request,
        )

    return WorkOrderADMonitoringRead.from_orm(row) if row else None


async def soft_delete_work_order_ad_monitoring(
    session: AsyncSession,
    work_order_id: int,
    *,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> bool:
    """Soft delete WorkOrderADMonitoring by ID."""
    result = await session.execute(
        select(WorkOrderADMonitoring)
        .where(WorkOrderADMonitoring.id == work_order_id)
        .where(WorkOrderADMonitoring.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
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
            record_id=work_order_id,
            action=AuditAction.DELETE,
            old_data=old_data_snapshot,
            new_data=None,
            current_user=audit_user,
            request=audit_request,
        )

    return True


async def soft_delete_work_order_ad_monitoring_by_ad(
    session: AsyncSession,
    work_order_id: int,
    ad_monitoring_id: int,
    *,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> bool:
    """Soft delete WorkOrderADMonitoring by ID scoped to ad_monitoring_id."""
    result = await session.execute(
        select(WorkOrderADMonitoring)
        .where(WorkOrderADMonitoring.id == work_order_id)
        .where(WorkOrderADMonitoring.ad_monitoring_fk == ad_monitoring_id)
        .where(WorkOrderADMonitoring.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
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
            record_id=work_order_id,
            action=AuditAction.DELETE,
            old_data=old_data_snapshot,
            new_data=None,
            current_user=audit_user,
            request=audit_request,
        )

    return True
