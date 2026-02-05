"""Shared upload directory (absolute path) so files are saved regardless of CWD."""
from pathlib import Path

# Absolute path: backend/uploads (same as backend/app/../uploads)
UPLOAD_DIR = (Path(__file__).resolve().parent.parent / "uploads").resolve()


def ensure_uploads_dir() -> None:
    """Create uploads directory if it does not exist."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
