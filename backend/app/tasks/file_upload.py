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
