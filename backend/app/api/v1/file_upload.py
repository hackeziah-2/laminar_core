"""Authenticated, bounded generic upload; existing URL and response keys retained."""
import asyncio
import weakref
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.formparsers import MultiPartException, MultiPartParser
from python_multipart.exceptions import MultipartParseError
from starlette.datastructures import UploadFile

from app.api.deps import oauth2_scheme, get_current_active_account, get_current_account, ensure_account_permission
from app.database import AsyncSessionLocal
from app.services import file_upload_service as storage

from app.core.rbac_modules import (MAINTENANCE_MODULE, LOGBOOK_MODULE, GENERAL_INFORMATION_MODULE, REGULATORY_COMPLIANCE_MODULE)

router = APIRouter()
MODULES = {
    'white_atl': MAINTENANCE_MODULE, 'dfp': MAINTENANCE_MODULE,
    'logbooks': LOGBOOK_MODULE, 'ad_monitoring': MAINTENANCE_MODULE,
    'document_on_board': GENERAL_INFORMATION_MODULE, 'aircraft': GENERAL_INFORMATION_MODULE,
    'aircraft_statutory_certificates': REGULATORY_COMPLIANCE_MODULE,
    'statutory_certificates': REGULATORY_COMPLIANCE_MODULE,
}
_slots = weakref.WeakKeyDictionary()


async def upload_owner(module_folder: str, token: str = Depends(oauth2_scheme)) -> int:
    module = MODULES.get(module_folder)
    if module is None:
        raise HTTPException(status_code=400, detail='Unsupported upload module.')
    # Auth session closes before multipart parsing or permanent storage starts.
    async with AsyncSessionLocal() as session:
        account = await get_current_account(token=token, session=session)
        account = await get_current_active_account(account=account)
        try:
            await ensure_account_permission(session, account, module, 'can_create')
        except HTTPException as exc:
            if exc.status_code != 403:
                raise
            await ensure_account_permission(session, account, module, 'can_update')
        return account.id


class _UploadParser(MultiPartParser):
    complete = False
    too_large = False
    part_bytes = 0

    def on_part_begin(self):
        super().on_part_begin()
        self.part_bytes = 0

    def on_headers_finished(self):
        super().on_headers_finished()
        file = self._current_part.file
        if file is not None:
            original = storage._validate_upload_file(file)
            extension = storage._validate_extension(original)
            storage._validate_declared_mime(file.content_type, extension)

    def on_part_data(self, data, start, end):
        self.part_bytes += end - start
        if self.part_bytes > storage.max_upload_bytes():
            self.too_large = True
            raise MultiPartException('File exceeds the upload size limit.')
        super().on_part_data(data, start, end)

    def on_end(self):
        self.complete = True
        super().on_end()


async def download_reader(module_folder: str, token: str = Depends(oauth2_scheme)) -> int:
    module = MODULES.get(module_folder)
    if module is None:
        raise HTTPException(status_code=404, detail='File not found')
    async with AsyncSessionLocal() as session:
        account = await get_current_account(token=token, session=session)
        account = await get_current_active_account(account=account)
        await ensure_account_permission(session, account, module, 'can_read')
        return account.id


async def _parse_file(request: Request):
    total = 0
    oversized = False
    limit = storage.max_upload_bytes() + storage.CHUNK_SIZE
    storage.reject_if_content_length_too_large(request.headers.get('content-length'))
    async def bounded_stream():
        nonlocal total, oversized
        async for chunk in request.stream():
            total += len(chunk)
            if total > limit:
                oversized = True
                raise MultiPartException('Upload request exceeds the size limit.')
            yield chunk
    if request.headers.get('content-type', '').split(';')[0].lower() != 'multipart/form-data':
        raise HTTPException(status_code=415, detail='Expected multipart/form-data.')
    parser = _UploadParser(request.headers, bounded_stream(), max_files=1, max_fields=0,
                             max_part_size=storage.CHUNK_SIZE)
    try:
        form = await asyncio.wait_for(parser.parse(), storage.upload_timeout_seconds())
        if not parser.complete:
            await form.close()
            raise HTTPException(status_code=400, detail="Incomplete multipart upload.")
        file = form.get('file')
        if not isinstance(file, UploadFile):
            await form.close()
            raise HTTPException(status_code=422, detail='Multipart field file is required.')
        return form, file
    except BaseException as exc:
        # Starlette closes these only for MultiPartException, not cancellation/disconnect.
        for file in parser._files_to_close_on_error:
            file.close()
        if isinstance(exc, MultiPartException):
            raise HTTPException(status_code=413 if oversized or parser.too_large else 400, detail=exc.message) from exc
        if isinstance(exc, (MultipartParseError, ValueError)):
            raise HTTPException(status_code=400, detail="Malformed multipart upload.") from exc
        if isinstance(exc, asyncio.TimeoutError):
            raise HTTPException(status_code=408, detail='Upload timed out. Please try again.') from exc
        raise


async def _register(owner_id: int, module_folder: str, result: dict) -> dict:
    from app.repository.upload_asset import register_upload
    return await register_upload(AsyncSessionLocal, owner_id, module_folder, result)


async def _finish_registration(owner_id, module_folder, result):
    from app.services.registered_upload_service import finish_registration
    return await finish_registration(owner_id, module_folder, result,
                                     session_factory=AsyncSessionLocal, register=_register)


@router.post('/api/v1/{module_folder}/upload', status_code=201, tags=['files'],
             summary='Upload a file', openapi_extra={'requestBody': {'required': True, 'content': {
                 'multipart/form-data': {'schema': {'type': 'object', 'required': ['file'],
                    'properties': {'file': {'type': 'string', 'format': 'binary'}}}}}}})
async def upload_file(request: Request, module_folder: str,
                      name: str | None = Query(None), owner_id: int = Depends(upload_owner)):
    """Store an authenticated module attachment.

    Purpose:
        Validate a bounded multipart upload and return its stored metadata.
    Business Rules:
        - Require an active account with module create or update permission.
        - Duplicate bytes reuse metadata only within the same owner and module.
    Args:
        request (Request): Multipart request containing one file.
        module_folder (str): Supported storage module.
        name (str | None): Optional filename suffix override.
        owner_id (int): Account ID established by authorization.
    Returns:
        dict: Existing upload response keys, with HTTP 201 for retries as well.
    Raises:
        HTTPException: 400/415/422 invalid input, 401/403 unauthorized,
            408 timeout, 413 oversized, 503 capacity exhausted.
    """
    override = name.strip() if name and name.strip() else None
    if override and ('..' in override or '/' in override or '\\' in override):
        raise HTTPException(status_code=400, detail='Invalid filename')
    loop = asyncio.get_running_loop()
    slots = _slots.setdefault(loop, asyncio.Semaphore(8))
    try:
        await asyncio.wait_for(slots.acquire(), timeout=1)
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=503, detail='Upload capacity reached. Please retry.',
                            headers={'Retry-After': '2'}) from exc
    try:
        form, file = await _parse_file(request)
        try:
            result = await storage.save_module_upload(file, module_folder, name_override=override,
                                                       include_checksum=True, track_pending=True)
        finally:
            await form.close()
        # Complete publication/metadata compensation even if the client disconnects now.
        job = asyncio.create_task(_finish_registration(owner_id, module_folder, result))
        try:
            return await asyncio.shield(job)
        except asyncio.CancelledError:
            while not job.done():
                try: await asyncio.shield(job)
                except asyncio.CancelledError: continue
                except Exception: break
            if not job.cancelled(): job.exception()
            raise
    finally:
        slots.release()
