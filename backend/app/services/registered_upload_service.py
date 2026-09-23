"""Reconcile file publication with metadata commits without a long DB transaction."""
import asyncio
import os
from app.models.upload_asset import UploadAsset
from app.services import file_upload_service as storage


async def finish_registration(owner_id, module_folder, result, *, session_factory, register):
    try:
        payload = await register(owner_id, module_folder, result)
    except BaseException:
        # A dropped COMMIT acknowledgement is ambiguous: verify using a new session.
        # If DB is unavailable retain the file, rather than deleting committed content.
        try:
            async with session_factory() as session:
                persisted = await session.get(UploadAsset, result['file_path'])
            if persisted is None:
                path = storage.resolve_stored_upload_path(result['file_path'])
                if path:
                    await asyncio.to_thread(path.unlink, missing_ok=True)
                    await asyncio.to_thread(path.with_name(path.name + '.pending').unlink, missing_ok=True)
        except Exception:
            storage.logger.exception('Upload registration recovery required for %s', result['file_path'])
        raise
    path = storage.resolve_stored_upload_path(result['file_path'])
    if path:
        if payload['file_path'] != result['file_path']:
            winner = (storage.UPLOAD_DIR / payload['file_path'].removeprefix('uploads/')).resolve()
            if not winner.is_relative_to(storage.UPLOAD_DIR.resolve()):
                raise RuntimeError('Invalid stored file location')
            if not winner.exists():
                try:
                    await asyncio.to_thread(os.link, path, winner)
                except FileExistsError:
                    pass  # Another duplicate request repaired it first.
            await asyncio.to_thread(path.unlink, missing_ok=True)
        await asyncio.to_thread(path.with_name(path.name + '.pending').unlink, missing_ok=True)
    return payload

