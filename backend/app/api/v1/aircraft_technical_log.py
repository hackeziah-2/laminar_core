import json
import uuid
from math import ceil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import (
    APIRouter,
    Depends,
    Query,
    HTTPException,
    status,
    Request,
)
from starlette.responses import Response
from pydantic import ValidationError

from sqlalchemy.ext.asyncio import AsyncSession

from app.upload_config import UPLOAD_DIR, ensure_uploads_dir
from app.schemas import aircraft_technical_log_schema
from app.core.atl_derived_times import (
    aircraft_technical_log_read_with_computed,
    resolve_auto_fields,
)
from app.repository.aircraft_technical_log import (
    list_aircraft_technical_logs,
    list_aircraft_technical_logs_manage,
    search_atl_by_sequence_no,
    get_aircraft_technical_log,
    get_latest_aircraft_technical_log,
    get_previous_atl,
    create_aircraft_technical_log,
    update_aircraft_technical_log,
    bulk_update_aircraft_technical_log_work_status,
    soft_delete_aircraft_technical_log,
    bulk_soft_delete_aircraft_technical_logs,
)
from app.api.deps import get_current_active_account
from app.database import get_session
from app.models.account import AccountInformation
from app.models.aircraft_techinical_log import WorkStatus


def _sanitize_filename(name: str) -> str:
    """Keep only safe filename characters; avoid path traversal."""
    if not name or not isinstance(name, str):
        return "upload"
    base = (name.split("/")[-1].split("\\")[-1] or "upload").strip()
    if not base or ".." in base:
        return "upload"
    return "".join(c for c in base if c.isalnum() or c in "._- ") or "upload"


def _round_optional_float_2(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


async def _save_atl_upload(form_file: Any, subdir: str) -> Optional[str]:
    """Save an uploaded file to uploads/<subdir>/ with a unique name. Returns stored path like 'white_atl/unique_name.pdf' or None if not a file."""
    if form_file is None:
        return None
    filename = getattr(form_file, "filename", None) if form_file else None
    if not filename or not getattr(form_file, "read", None):
        return None
    ensure_uploads_dir()
    target_dir = UPLOAD_DIR / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_base = _sanitize_filename(filename)
    unique_name = f"{uuid.uuid4().hex}_{safe_base}"
    path = target_dir / unique_name
    content = await form_file.read()
    path.write_bytes(content)
    return f"{subdir}/{unique_name}"


router = APIRouter(
    prefix="/api/v1/aircraft-technical-log",
    tags=["aircraft-technical-log"]
)


def _atl_update_openapi_request_body() -> dict:
    """OpenAPI requestBody for PUT: handler uses Request (JSON or multipart), so body is not auto-generated."""
    return {
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": aircraft_technical_log_schema.AircraftTechnicalLogUpdate.schema()
                },
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "description": "Send `data` or `json_data` as a JSON string of the same fields as application/json. Optional file fields white_atl, dfp.",
                        "properties": {
                            "data": {
                                "type": "string",
                                "description": "Stringified JSON object (AircraftTechnicalLogUpdate fields).",
                            },
                            "json_data": {
                                "type": "string",
                                "description": "Alias for `data`.",
                            },
                            "white_atl": {
                                "type": "string",
                                "format": "binary",
                            },
                            "dfp": {
                                "type": "string",
                                "format": "binary",
                            },
                        },
                    }
                },
            }
        }
    }


@router.get("/paged")
async def api_list_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    search: Optional[str] = None,
    aircraft_fk: Optional[int] = Query(None, description="Filter by aircraft ID"),
    work_status: Optional[WorkStatus] = Query(
        None,
        description=(
            "Filter by work status (e.g. work_status=APPROVED). "
            "Values: FOR_REVIEW, REJECTED_MAINTENANCE, APPROVED, AWAITING_ATTACHMENT, "
            "REJECTED_QUALITY, PENDING, COMPLETED. Omit for no filter."
        ),
    ),
    atl_batch: Optional[int] = Query(
        None,
        description="Filter by ATL batch id (same as atl_batch_fk).",
    ),
    atl_batch_fk: Optional[int] = Query(
        None,
        description="Filter by ATL batch id.",
    ),
    sort: str = Query(
        "-sequence_no",
        description="Sort fields (prefix - for desc). Default: -sequence_no. Example: -created_at,sequence_no",
    ),
    session: AsyncSession = Depends(get_session),
    _current_account: AccountInformation = Depends(get_current_active_account),
):
    """Get paginated list of Aircraft Technical Log entries. auto_* fields are read from persisted columns."""
    offset = (page - 1) * limit
    batch_filter = atl_batch_fk if atl_batch_fk is not None else atl_batch
    items, total = await list_aircraft_technical_logs(
        session=session,
        limit=limit,
        offset=offset,
        search=search,
        aircraft_fk=aircraft_fk,
        atl_batch_fk=batch_filter,
        work_status=work_status,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0

    result_items = [
        aircraft_technical_log_schema.ATLPagedItemWithAuto.from_orm(item).dict()
        for item in items
    ]

    return {
        "items": result_items,
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get(
    "/search",
    response_model=List[aircraft_technical_log_schema.ATLSearchItem]
)
async def api_search_by_sequence(
    search: Optional[str] = Query(None, description="Search by ATL Sequence Number"),
    aircraft_id: Optional[int] = Query(None, description="Filter by aircraft ID (e.g. when on aircraft-scoped TCC form)"),
    session: AsyncSession = Depends(get_session)
):
    """Search by ATL Sequence Number for ATL Reference (CPCP Add/Edit, TCC, etc.). Accepts 'ATL-24451' or '24451'. Returns id (atl_ref), sequence_no, tachometer_end, auto_airframe_aftt (cumulative), origin_date, search_display (formatted one-line label), sequence_no_display, aircraft."""
    if not search or not str(search).strip():
        return []
    items = await search_atl_by_sequence_no(
        session, search=search.strip(), aircraft_fk=aircraft_id
    )
    memo: Dict[Tuple[int, str, Optional[int]], Dict[str, float]] = {}
    out: List[aircraft_technical_log_schema.ATLSearchItem] = []
    for item in items:
        aircraft_obj = getattr(item, "aircraft", None)
        auto = await resolve_auto_fields(session, item, aircraft_obj, memo)
        out.append(
            aircraft_technical_log_schema.ATLSearchItem(
                id=item.id,
                sequence_no=str(item.sequence_no).strip() if item.sequence_no is not None else "",
                tachometer_end=_round_optional_float_2(item.tachometer_end),
                auto_airframe_aftt=_round_optional_float_2(auto.get("auto_airframe_aftt")),
                origin_date=item.origin_date,
                aircraft=aircraft_technical_log_schema.AircraftRead.from_orm(aircraft_obj),
            )
        )
    return out


@router.get(
    "/latest",
    response_model=aircraft_technical_log_schema.AircraftTechnicalLogRead
)
async def api_get_latest(
    aircraft_fk: Optional[int] = Query(None, description="Filter by aircraft ID"),
    batch_id: Optional[int] = Query(
        None,
        description="Filter by ATL batch id (atl_batch.id / atl_batch_fk).",
    ),
    atl_batch: Optional[int] = Query(
        None,
        description="Filter by ATL batch id (same as batch_id).",
    ),
    atl_batch_fk: Optional[int] = Query(
        None,
        description="Filter by ATL batch id.",
    ),
    sequence_no: Optional[str] = Query(
        None,
        description=(
            "When set, return the nearest previous ATL (highest sequence_no strictly less than this value) "
            "for the same aircraft_fk and optional batch. Accepts 'ATL-1006' or '1006'."
        ),
    ),
    session: AsyncSession = Depends(get_session),
):
    """Latest ATL by highest sequence_no, or previous ATL when sequence_no is provided."""
    batch_filter = (
        atl_batch_fk
        if atl_batch_fk is not None
        else (atl_batch if atl_batch is not None else batch_id)
    )
    if sequence_no is not None:
        if aircraft_fk is None:
            raise HTTPException(
                status_code=422,
                detail="aircraft_fk is required when sequence_no is provided",
            )
        obj = await get_previous_atl(
            session,
            aircraft_fk,
            sequence_no,
            atl_batch_fk=batch_filter,
            null_batch_only_when_batch_unset=False,
        )
        if not obj:
            raise HTTPException(
                status_code=404,
                detail="No previous Aircraft Technical Log entry found for the given sequence_no",
            )
    else:
        obj = await get_latest_aircraft_technical_log(
            session,
            aircraft_fk=aircraft_fk,
            atl_batch_fk=batch_filter,
        )
        if not obj:
            raise HTTPException(
                status_code=404,
                detail="No Aircraft Technical Log entries found",
            )
    return await aircraft_technical_log_read_with_computed(session, obj)


@router.get("/manage/paged")
async def api_atl_list_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    search: Optional[str] = None,
    aircraft_fk: Optional[int] = Query(None, description="Filter by aircraft ID"),
    work_status: Optional[WorkStatus] = Query(
        None,
        description=(
            "Filter by work status (e.g. work_status=APPROVED). "
            "Values: FOR_REVIEW, REJECTED_MAINTENANCE, APPROVED, AWAITING_ATTACHMENT, "
            "REJECTED_QUALITY, PENDING, COMPLETED. Omit for no filter."
        ),
    ),
    atl_batch: Optional[int] = Query(
        None,
        description="Filter by ATL batch id (same as atl_batch_fk).",
    ),
    atl_batch_fk: Optional[int] = Query(
        None,
        description="Filter by ATL batch id.",
    ),
    sort: str = Query(
        "-sequence_no",
        description="Sort fields (prefix - for desc). Default: -sequence_no. Example: -created_at,sequence_no",
    ),
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Get paginated list of Aircraft Technical Log entries (manage). auto_* from persisted columns."""
    offset = (page - 1) * limit
    batch_filter = atl_batch_fk if atl_batch_fk is not None else atl_batch
    items, total = await list_aircraft_technical_logs_manage(
        session=session,
        limit=limit,
        offset=offset,
        search=search,
        aircraft_fk=aircraft_fk,
        atl_batch_fk=batch_filter,
        work_status=work_status,
        sort=sort,
        current_account=current_account,
    )
    pages = ceil(total / limit) if total else 0

    result_items = [
        aircraft_technical_log_schema.ATLPagedItemWithAuto.from_orm(item).dict()
        for item in items
    ]

    return {
        "items": result_items,
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get(
    "/{log_id}",
    response_model=aircraft_technical_log_schema.AircraftTechnicalLogRead
)
async def api_get(
    log_id: int,
    recompute: bool = Query(
        False,
        description=(
            "When true, recompute auto_* from the full predecessor chain even if "
            "persisted auto_* columns exist on the row."
        ),
    ),
    session: AsyncSession = Depends(get_session),
):
    """Get a single Aircraft Technical Log entry by ID."""
    obj = await get_aircraft_technical_log(session, log_id)
    if not obj:
        raise HTTPException(
            status_code=404,
            detail="Aircraft Technical Log not found"
        )
    return await aircraft_technical_log_read_with_computed(
        session, obj, recompute=recompute
    )


@router.post(
    "/",
    response_model=aircraft_technical_log_schema.AircraftTechnicalLogRead,
    status_code=status.HTTP_201_CREATED
)
async def api_create(
    payload: aircraft_technical_log_schema.AircraftTechnicalLogCreate,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Create a new Aircraft Technical Log entry."""
    entry = await create_aircraft_technical_log(
        session, payload, audit_account_id=current_account.id
    )
    return await aircraft_technical_log_read_with_computed(session, entry)


async def _parse_update_payload(request: Request) -> aircraft_technical_log_schema.AircraftTechnicalLogUpdate:
    """Parse request body as either JSON or multipart form with 'data'/'json_data' JSON string (for file upload)."""
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if content_type == "application/json":
        body = await request.body()
        if not body:
            raise HTTPException(status_code=422, detail="Request body is required")
        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=422, detail=f"Invalid JSON: {e}")
    elif content_type == "multipart/form-data":
        form = await request.form()
        data_str = form.get("data") or form.get("json_data")
        if data_str is None:
            raise HTTPException(
                status_code=422,
                detail="Multipart form must include 'data' or 'json_data' field with JSON payload",
            )
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=422, detail=f"Invalid JSON in data/json_data: {e}")
        # Handle White ATL and DFP file uploads (form fields 'white_atl' and 'dfp')
        white_atl_file = form.get("white_atl")
        dfp_file = form.get("dfp")
        if white_atl_file:
            saved = await _save_atl_upload(white_atl_file, "white_atl")
            if saved:
                data["white_atl"] = saved
        if dfp_file:
            saved = await _save_atl_upload(dfp_file, "dfp")
            if saved:
                data["dfp"] = saved
    else:
        raise HTTPException(
            status_code=415,
            detail="Content-Type must be application/json or multipart/form-data",
        )
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="Payload must be a JSON object")
    try:
        return aircraft_technical_log_schema.AircraftTechnicalLogUpdate(**data)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.put(
    "/{log_id}",
    response_model=aircraft_technical_log_schema.AircraftTechnicalLogRead,
    openapi_extra=_atl_update_openapi_request_body(),
)
async def api_update(
    log_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Update an Aircraft Technical Log entry. Accepts application/json body or multipart/form-data with 'data' or 'json_data' (JSON string). For multipart, optional form fields 'white_atl' and 'dfp' are file uploads; saved under uploads/white_atl/ and uploads/dfp/. Download via GET /api/v1/white_atl/download?name=<filename> and /api/v1/dfp/download?name=<filename>."""
    log_in = await _parse_update_payload(request)
    updated = await update_aircraft_technical_log(
        session=session,
        log_id=log_id,
        log_in=log_in,
        audit_account_id=current_account.id,
        current_account=current_account,
    )

    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Aircraft Technical Log not found"
        )

    return await aircraft_technical_log_read_with_computed(session, updated)


@router.put(
    "/work-status/bulk",
    response_model=aircraft_technical_log_schema.AircraftTechnicalLogBulkWorkStatusUpdateResponse,
)
async def api_bulk_update_work_status(
    payload: aircraft_technical_log_schema.AircraftTechnicalLogBulkWorkStatusUpdateRequest,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Bulk update ATL work_status by explicit ATL IDs."""
    return await bulk_update_aircraft_technical_log_work_status(
        session=session,
        atl_ids=payload.ids,
        work_status=payload.work_status,
        atomic=payload.atomic,
        audit_account_id=current_account.id,
        current_account=current_account,
    )


@router.delete(
    "/bulk",
    response_model=aircraft_technical_log_schema.AircraftTechnicalLogBulkDeleteResponse,
)
async def api_bulk_delete(
    payload: aircraft_technical_log_schema.AircraftTechnicalLogBulkDeleteRequest,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    """Bulk soft delete ATL entries by explicit ATL IDs."""
    return await bulk_soft_delete_aircraft_technical_logs(
        session=session,
        atl_ids=payload.ids,
        atomic=payload.atomic,
        audit_account_id=current_account.id,
    )


@router.delete(
    "/{log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def api_delete(
    log_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Soft delete an Aircraft Technical Log entry."""
    deleted = await soft_delete_aircraft_technical_log(session, log_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aircraft Technical Log not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
