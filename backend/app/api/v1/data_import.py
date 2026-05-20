"""Excel/CSV import endpoints (registry-driven, thin HTTP layer)."""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_account_permission, get_current_active_account
from app.core.exceptions import AppError
from app.data_imports import (
    ensure_import_targets_loaded,
    get_import_target,
    list_import_targets,
    resolve_import_target_key,
)
from app.data_imports.definitions import ExcelImportTarget
from app.database import get_session
from app.models.account import AccountInformation
from app.schemas.data_import_schema import ExcelImportResult, ImportTargetInfo
from app.services.excel_import.config import ExcelImportConfig
from app.services.excel_import_service import ExcelImportService

router = APIRouter(
    prefix="/api/v1/excel-data",
    tags=["excel-data"],
)


def _http_status_for_app_error(exc: AppError) -> int:
    if exc.code == "not_found":
        return status.HTTP_404_NOT_FOUND
    if exc.code == "permission_denied":
        return status.HTTP_403_FORBIDDEN
    return status.HTTP_400_BAD_REQUEST


def _target_to_info(target: ExcelImportTarget) -> ImportTargetInfo:
    return ImportTargetInfo(
        key=target.key,
        label=target.label,
        summary=target.summary,
        rbac_module=target.rbac_module,
        required_form_fields=list(target.required_form_fields),
        optional_form_fields=list(target.optional_form_fields),
        legacy_paths=list(target.legacy_paths),
    )


def _form_data_from_request(form: Mapping[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in form.items() if k != "file"}


async def _run_registered_import(
    *,
    target: ExcelImportTarget,
    file: UploadFile,
    dry_run: bool,
    form_data: Dict[str, Any],
    session: AsyncSession,
    current_account: AccountInformation,
) -> ExcelImportResult:
    inject_fields: Dict[str, Any] = {}
    if target.resolve_context is not None:
        try:
            inject_fields = await target.resolve_context(session, form_data)
        except AppError as exc:
            raise HTTPException(
                status_code=_http_status_for_app_error(exc),
                detail=exc.message,
            ) from exc

    config = ExcelImportConfig(
        model=target.model,
        schema=target.schema,
        unique_fields=target.unique_fields,
        hook_key=target.hook_key,
        dry_run=dry_run,
        column_mapping=target.column_mapping,
        integrity_error_messages=target.integrity_error_messages,
        inject_fields=inject_fields,
        audit_account_id=current_account.id,
    )
    try:
        result = await ExcelImportService.run(file, session, config)
    except AppError as exc:
        raise HTTPException(
            status_code=_http_status_for_app_error(exc),
            detail=exc.message,
        ) from exc
    return ExcelImportResult.from_service_dict(result)


# Single import route: /{target_key}/import (keys from GET /targets, e.g. aircraft, aircraft-technical-log).


@router.get(
    "/targets",
    response_model=List[ImportTargetInfo],
    summary="List registered Excel import targets",
)
async def list_excel_import_targets(
    current_account: AccountInformation = Depends(get_current_active_account),
):
    ensure_import_targets_loaded()
    return [_target_to_info(t) for t in list_import_targets()]


@router.post(
    "/{target_key}/import",
    response_model=ExcelImportResult,
    summary="Import rows for a registered target",
    description=(
        "Dynamic import endpoint. Use GET /targets for available `target_key` values. "
        "Some targets require multipart form fields (e.g. ATL needs batch_id and aircraft_id or registration)."
    ),
)
async def import_excel_by_target(
    target_key: str,
    request: Request,
    file: UploadFile = File(..., description="Excel (.xlsx, .xls) or CSV file"),
    dry_run: bool = Query(False, description="If true, validate only and return counts without writing"),
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    ensure_import_targets_loaded()
    resolved_key = resolve_import_target_key(target_key)
    if resolved_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown import target: {target_key}",
        )
    target = get_import_target(resolved_key)
    assert target is not None

    await ensure_account_permission(
        session, current_account, target.rbac_module, target.rbac_action
    )

    form = await request.form()
    return await _run_registered_import(
        target=target,
        file=file,
        dry_run=dry_run,
        form_data=_form_data_from_request(form),
        session=session,
        current_account=current_account,
    )
