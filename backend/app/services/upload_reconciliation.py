"""Recover stale pending files after crashes or uncertain database commits."""
import time
from sqlalchemy import or_, select
from app.database import AsyncSessionLocal, Base
from app.models.upload_asset import UploadAsset  # register metadata for worker-only imports
from app.services import file_upload_service as storage


async def reconcile_uploads(min_age_seconds=24 * 3600):
    # Never touch legacy files without a marker. A failed DB check preserves data.
    cutoff = time.time() - min_age_seconds
    removed = 0
    for pending in storage.UPLOAD_DIR.rglob('*.pending'):
        if pending.is_symlink() or pending.stat().st_mtime >= cutoff:
            continue
        path = pending.with_name(pending.name[:-8])
        if not path.resolve().is_relative_to(storage.UPLOAD_DIR.resolve()):
            continue
        relative = path.relative_to(storage.UPLOAD_DIR).as_posix()
        forms = [relative, 'uploads/' + relative, '/app/uploads/' + relative, str(path), path.name]
        referenced = False
        async with AsyncSessionLocal() as session:
            # Include generic metadata and existing attachment columns; no byte content.
            for table in Base.metadata.tables.values():
                columns = [c for c in table.columns if c.name in {
                    'file_path', 'temp_file_path', 'upload_file', 'engine_arc', 'propeller_arc', 'white_atl', 'dfp'}]
                if columns and await session.scalar(select(1).select_from(table).where(
                    or_(*(c.in_(forms) for c in columns))).limit(1)):
                    referenced = True
                    break
        if not referenced:
            path.unlink(missing_ok=True)
            removed += 1
        pending.unlink(missing_ok=True)
    for part in storage.UPLOAD_DIR.rglob('.upload-*.part'):
        if not part.is_symlink() and part.stat().st_mtime < cutoff:
            part.unlink(missing_ok=True)
            removed += 1
    return removed
