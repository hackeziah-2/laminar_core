"""Background post-upload work. The HTTP handler returns as soon as the file is stored."""
from __future__ import annotations

import logging

from app.services.file_upload_service import resolve_stored_upload_path
from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.file_upload.finalize_uploaded_file")
def finalize_uploaded_file(file_path: str, size_bytes: int) -> bool:
    """Confirm the stored file exists without blocking the upload response."""
    resolved = resolve_stored_upload_path(file_path)
    if resolved is None:
        logger.warning(
            "Post-upload finalize skipped; file missing: %s (%s bytes)",
            file_path,
            size_bytes,
        )
        return False
    logger.info("Upload stored at %s (%s bytes)", resolved, size_bytes)
    return True


@celery_app.task(name="app.tasks.file_upload.process_atl_import")
def process_atl_import(job_id: str) -> None:
    """Parse and import in a separate worker process with its own event loop."""
    import asyncio
    from app.database import engine, AsyncSessionLocal
    from sqlalchemy import update
    from app.models.atl_excel_import_job import AtlExcelImportJob
    from app.services.atl_excel_import_job_runner import process_atl_excel_import_job
    async def run():
        try:
            async with AsyncSessionLocal() as session:
                claim = await session.execute(update(AtlExcelImportJob).where(
                    AtlExcelImportJob.job_id == job_id, AtlExcelImportJob.status == "PENDING"
                ).values(status="PROCESSING", message="Processing upload"))
                await session.commit()
                if claim.rowcount != 1:
                    return
            await process_atl_excel_import_job(job_id)
        finally:
            await engine.dispose()
    asyncio.run(run())


def enqueue_atl_import(job_id: str) -> None:
    try:
        process_atl_import.apply_async(args=[job_id], retry=False)
    except Exception:
        logger.exception("Import remains PENDING for periodic dispatch: %s", job_id)


@celery_app.task(name="app.tasks.file_upload.dispatch_pending_imports")
def dispatch_pending_imports():
    import asyncio
    from sqlalchemy import select
    from app.database import AsyncSessionLocal, engine
    from app.models.atl_excel_import_job import AtlExcelImportJob
    async def pending():
        try:
            async with AsyncSessionLocal() as session:
                return list((await session.scalars(select(AtlExcelImportJob.job_id).where(
                    AtlExcelImportJob.status == "PENDING").limit(100))).all())
        finally:
            await engine.dispose()
    for job_id in asyncio.run(pending()):
        enqueue_atl_import(job_id)


@celery_app.task(name="app.tasks.file_upload.reconcile_uploads")
def reconcile_uploads():
    import asyncio
    from app.database import engine
    from app.services.upload_reconciliation import reconcile_uploads as reconcile
    async def run():
        try:
            return await reconcile()
        finally:
            await engine.dispose()
    return asyncio.run(run())
