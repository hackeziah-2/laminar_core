"""ATL White ATL / DFP uploads must not require Maintenance can_update."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.file_upload import ensure_any_folder_permission
from app.core.rbac_modules import MAINTENANCE_MODULE, OPERATION_MODULE


@pytest.mark.asyncio
async def test_white_atl_upload_allows_operation_update_without_maintenance():
    account = object()
    session = object()

    async def _check(_session, _account, module, action):
        if module == OPERATION_MODULE and action == "can_update":
            return
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied: {action} on {module}",
        )

    with patch(
        "app.api.v1.file_upload.ensure_account_permission",
        new=AsyncMock(side_effect=_check),
    ):
        await ensure_any_folder_permission(
            session, account, "white_atl", ("can_create", "can_update")
        )


@pytest.mark.asyncio
async def test_white_atl_upload_still_rejects_when_no_atl_module_can_update():
    with patch(
        "app.api.v1.file_upload.ensure_account_permission",
        new=AsyncMock(
            side_effect=HTTPException(
                status_code=403,
                detail=f"Permission denied: can_update on {MAINTENANCE_MODULE}",
            )
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await ensure_any_folder_permission(
                object(), object(), "dfp", ("can_create", "can_update")
            )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_logbook_upload_still_requires_the_logbook_module():
    async def _check(_session, _account, module, action):
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied: {action} on {module}",
        )

    with patch(
        "app.api.v1.file_upload.ensure_account_permission",
        new=AsyncMock(side_effect=_check),
    ) as mocked:
        with pytest.raises(HTTPException):
            await ensure_any_folder_permission(
                object(), object(), "logbooks", ("can_create", "can_update")
            )
    modules = {call.args[2] for call in mocked.await_args_list}
    assert modules == {"Logbook"}
    assert MAINTENANCE_MODULE not in modules
