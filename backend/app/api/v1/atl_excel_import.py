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
    Query,
    UploadFile,
    status,
)
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_account, require_permission
from app.core.exceptions import AppError
from app.core.rbac_modules import MAINTENANCE_MODULE
from app.database import get_session
from app.models.account import AccountInformation
from app.repository.atl_excel_import_job import create_import_job, get_import_job
from app.repository.import_prerequisites import ensure_atl_batch_exists, resolve_aircraft_id
from app.schemas.atl_excel_import_job_schema import (
    AtlExcelImportProgressResponse,
    AtlExcelImportStartResponse,
)
from app.services.atl_excel_import_job_runner import process_atl_excel_import_job
from app.services.atl_excel_import_progress import build_import_progress_payload
from app.services.excel_import.validation_errors import (
    format_error_report_csv,
    format_error_report_markdown,
)
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
    current_account: AccountInformation = Depends(
        require_permission(MAINTENANCE_MODULE, "can_create")
    ),
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

    try:
        resolved_id = await resolve_aircraft_id(
            session,
            aircraft_id=_parse_form_optional_int(aircraft_id),
            registration=str(registration).strip() if registration else None,
        )
        await ensure_atl_batch_exists(session, resolved_batch_id)
    except AppError as exc:
        code = 404 if exc.code == "not_found" else 400
        raise HTTPException(status_code=code, detail=exc.message) from exc

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
    _: AccountInformation = Depends(require_permission(MAINTENANCE_MODULE, "can_read")),
):
    job = await get_import_job(session, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")

    return AtlExcelImportProgressResponse(**build_import_progress_payload(job))


@router.get(
    "/import-progress/{job_id}/errors",
    summary="Download ATL Excel import validation errors",
)
async def download_atl_excel_import_errors(
    job_id: str,
    format: str = Query("csv", pattern="^(csv|markdown|json)$"),
    session: AsyncSession = Depends(get_session),
    _: AccountInformation = Depends(require_permission(MAINTENANCE_MODULE, "can_read")),
):
    job = await get_import_job(session, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")

    errors = job.errors if isinstance(job.errors, list) else []
    if not errors:
        raise HTTPException(status_code=404, detail="No validation errors for this import job")

    if format == "json":
        return {"errors": errors, "message": job.message}

    if format == "markdown":
        body = format_error_report_markdown(errors)
        return PlainTextResponse(
            content=body,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="atl-import-errors-{job_id}.md"'},
        )

    body = format_error_report_csv(errors)
    return Response(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="atl-import-errors-{job_id}.csv"'},
    )
