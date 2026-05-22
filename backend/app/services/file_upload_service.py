"""Enterprise file upload: UUID storage names, validation, and HTTP-mapped errors."""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile, status

from app.upload_config import UPLOAD_DIR, ensure_uploads_dir

# Default 50 MiB; override with MAX_UPLOAD_BYTES env (integer bytes)
_DEFAULT_MAX_BYTES = 50 * 1024 * 1024
_CHUNK_SIZE = 1024 * 1024


def max_upload_bytes() -> int:
    raw = os.getenv("MAX_UPLOAD_BYTES", "").strip()
    if not raw:
        return _DEFAULT_MAX_BYTES
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_MAX_BYTES
    return value if value > 0 else _DEFAULT_MAX_BYTES


def is_safe_module_folder(name: str) -> bool:
    """Allow only alphanumeric, underscore, hyphen (no path traversal)."""
    return bool(name) and all(c.isalnum() or c in "_-" for c in name)


def sanitize_filename(name: str) -> str:
    """Strip path segments and unsafe characters from a client-provided name."""
    if not name or not isinstance(name, str):
        return "upload"
    base = (name.split("/")[-1].split("\\")[-1] or "upload").strip()
    if not base or ".." in base:
        return "upload"
    safe = "".join(c for c in base if c.isalnum() or c in "._- ")
    return safe or "upload"


def build_storage_filename(original_name: str, *, name_override: Optional[str] = None) -> str:
    """Return `{uuid}_{sanitized_base}` so stored files are unique and non-guessable."""
    base = sanitize_filename(name_override or original_name or "upload")
    return f"{uuid.uuid4().hex}_{base}"


def _validate_upload_file(file: UploadFile) -> str:
    if not file or not getattr(file, "read", None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided",
        )
    original = (file.filename or "").strip()
    if not original:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must include a filename",
        )
    return original


async def _write_upload_to_path(
    upload_file: UploadFile,
    dest_path: Path,
    *,
    max_bytes: int,
) -> int:
    """Stream upload to disk with a size cap; remove partial file on failure."""
    total = 0
    try:
        with dest_path.open("wb") as out:
            while True:
                chunk = await upload_file.read(_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"File exceeds maximum allowed size ({max_bytes} bytes)",
                    )
                out.write(chunk)
    except HTTPException:
        dest_path.unlink(missing_ok=True)
        raise
    except OSError as exc:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {exc}",
        ) from exc
    return total


async def save_module_upload(
    upload_file: UploadFile,
    module_folder: str,
    *,
    name_override: Optional[str] = None,
    max_bytes: Optional[int] = None,
) -> dict:
    """
    Persist an upload under uploads/{module_folder}/ with a UUID-prefixed filename.

    Returns dict with file_path (relative), filename, size_bytes, content_type.
    """
    if not is_safe_module_folder(module_folder):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid module folder name",
        )

    limit = max_bytes if max_bytes is not None else max_upload_bytes()
    original_name = _validate_upload_file(upload_file)
    storage_name = build_storage_filename(original_name, name_override=name_override)

    ensure_uploads_dir()
    target_dir = (UPLOAD_DIR / module_folder).resolve()
    if not str(target_dir).startswith(str(UPLOAD_DIR.resolve())):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid upload destination",
        )
    target_dir.mkdir(parents=True, exist_ok=True)

    dest_path = target_dir / storage_name
    size_bytes = await _write_upload_to_path(upload_file, dest_path, max_bytes=limit)

    if size_bytes == 0:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    relative = f"{module_folder}/{storage_name}"
    return {
        "file_path": f"uploads/{relative}",
        "filename": storage_name,
        "size_bytes": size_bytes,
        "content_type": upload_file.content_type,
    }
