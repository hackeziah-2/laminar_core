"""Shared upload directory (absolute path) so files are saved regardless of CWD."""
from pathlib import Path

# Absolute path: backend/uploads (same as backend/app/../uploads)
UPLOAD_DIR = (Path(__file__).resolve().parent.parent / "uploads").resolve()

ATL_IMPORT_JOBS_DIR = UPLOAD_DIR / "atl_import_jobs"


def ensure_uploads_dir() -> None:
    """Create uploads directory if it does not exist."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def ensure_atl_import_jobs_dir() -> None:
    """Subfolder for temporary ATL Excel import uploads (deleted after processing)."""
    ensure_uploads_dir()
    ATL_IMPORT_JOBS_DIR.mkdir(parents=True, exist_ok=True)
