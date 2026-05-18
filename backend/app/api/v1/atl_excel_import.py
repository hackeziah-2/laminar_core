"""ATL Excel import with async job progress (POST /import-excel, GET /import-progress/{job_id})."""
import uuid
from pathlib import Path
from typing import Optional, Union

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_account
from app.database import get_session
from app.models.account import AccountInformation
from app.models.aircraft import Aircraft
from app.models.atl_batch import AtlBatch
from app.repository.atl_excel_import_job import create_import_job, get_import_job
from app.schemas.atl_excel_import_job_schema import (
    AtlExcelImportProgressResponse,
    AtlExcelImportStartResponse,
)
from app.services.atl_excel_import_job_runner import process_atl_excel_import_job
from app.upload_config import ATL_IMPORT_JOBS_DIR, ensure_atl_import_jobs_dir

router = APIRouter(prefix="/api/v1", tags=["atl-excel-import"])


def _parse_form_optional_int(value: Union[str, int, None]) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


@router.post(
    "/import-excel",
    response_model=AtlExcelImportStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start ATL Excel import (background job)",
)
async def start_atl_excel_import(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Excel .xlsx or .xls"),
    aircraft_id: Optional[str] = Form(None, description="Aircraft ID for all rows"),
    registration: Optional[str] = Form(None, description="Aircraft registration if aircraft_id omitted"),
    batch_id: str = Form(..., description="atl_batch.id applied to every imported row"),
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    fn = (file.filename or "").lower()
    if not fn.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400,
            detail="Only .xlsx or .xls files are allowed for this import.",
        )

    resolved_batch_id = _parse_form_optional_int(batch_id)
    if resolved_batch_id is None:
        raise HTTPException(
            status_code=400,
            detail="batch_id is required and must be a valid integer (atl_batch.id).",
        )

    aid = _parse_form_optional_int(aircraft_id)
    reg = str(registration).strip() if registration else ""

    if aid is not None:
        result = await session.execute(
            select(Aircraft).where(Aircraft.id == aid).where(Aircraft.is_deleted.is_(False))
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Aircraft with this ID not found")
        resolved_id = aid
    elif reg:
        result = await session.execute(
            select(Aircraft).where(Aircraft.registration.ilike(reg)).where(Aircraft.is_deleted.is_(False))
        )
        aircraft = result.scalar_one_or_none()
        if aircraft is None:
            raise HTTPException(
                status_code=404,
                detail=f"Aircraft with registration '{reg}' not found",
            )
        resolved_id = aircraft.id
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either aircraft_id or registration",
        )

    b = await session.execute(
        select(AtlBatch).where(AtlBatch.id == resolved_batch_id).where(AtlBatch.is_deleted.is_(False))
    )
    if b.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="ATL batch not found")

    ensure_atl_import_jobs_dir()
    job_id = str(uuid.uuid4())
    suffix = Path(fn).suffix or ".xlsx"
    dest_path = ATL_IMPORT_JOBS_DIR / f"{job_id}{suffix}"

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    dest_path.write_bytes(contents)

    await create_import_job(
        session,
        job_id=job_id,
        temp_file_path=str(dest_path),
        aircraft_fk=resolved_id,
        atl_batch_fk=resolved_batch_id,
        started_by=current_account.id,
        status="PENDING",
        message="Queued for processing",
    )
    await session.commit()

    background_tasks.add_task(process_atl_excel_import_job, job_id)

    return AtlExcelImportStartResponse(
        job_id=job_id,
        status="PENDING",
        message="Import job queued. Poll GET /api/v1/import-progress/{job_id} for status.",
    )


@router.get(
    "/import-progress/{job_id}",
    response_model=AtlExcelImportProgressResponse,
    summary="ATL Excel import job progress",
)
async def get_atl_excel_import_progress(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    _: AccountInformation = Depends(get_current_active_account),
):
    job = await get_import_job(session, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")

    total = job.total_rows or 0
    if total > 0:
        progress = round(100.0 * job.processed_rows / total, 2)
    else:
        progress = 100.0 if job.status == "COMPLETED" else 0.0

    errors = job.errors if isinstance(job.errors, list) else []

    return AtlExcelImportProgressResponse(
        job_id=job.job_id,
        progress=progress,
        status=job.status,
        message=job.message,
        total_rows=job.total_rows,
        processed_rows=job.processed_rows,
        failed_rows=job.failed_rows,
        errors=errors,
    )
