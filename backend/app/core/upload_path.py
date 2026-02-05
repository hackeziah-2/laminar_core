"""Shared absolute upload directory so files are saved in one place regardless of CWD."""
from pathlib import Path

# backend/app/core/upload_path.py -> backend/uploads (absolute)
UPLOAD_DIR = (Path(__file__).resolve().parent.parent.parent / "uploads").resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
