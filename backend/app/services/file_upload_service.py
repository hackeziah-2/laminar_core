"""Streamed file uploads: chunked I/O, size/type checks, unique names, fail-safe cleanup."""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import HTTPException, UploadFile, status

from app.upload_config import UPLOAD_DIR, ensure_uploads_dir

logger = logging.getLogger(__name__)

DEFAULT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024
DEFAULT_UPLOAD_TIMEOUT_SECONDS = 120.0

MAX_FILE_SIZE = DEFAULT_MAX_UPLOAD_BYTES

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".csv",
}

_EXT_TO_MIMES = {
    ".pdf": {"application/pdf"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".gif": {"image/gif"},
    ".webp": {"image/webp"},
    ".doc": {"application/msword"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    },
    ".xls": {"application/vnd.ms-excel"},
    ".xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    },
    ".csv": {
        "text/csv",
        "text/plain",
        "application/csv",
        "application/vnd.ms-excel",
    },
}

_BINARY_SNIFFED_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "application/zip",
    "application/msword",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

_GENERIC_DECLARED_MIMES = {
    "",
    "application/octet-stream",
    "binary/octet-stream",
}


def max_upload_bytes() -> int:
    raw = os.getenv("MAX_UPLOAD_BYTES", "").strip()
    if not raw:
        return DEFAULT_MAX_UPLOAD_BYTES
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_UPLOAD_BYTES
    return value if value > 0 else DEFAULT_MAX_UPLOAD_BYTES


def upload_timeout_seconds() -> float:
    raw = os.getenv("UPLOAD_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return DEFAULT_UPLOAD_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_UPLOAD_TIMEOUT_SECONDS
    return value if value > 0 else DEFAULT_UPLOAD_TIMEOUT_SECONDS


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


def sniff_content_type(header: bytes, extension: str) -> str:
    """Detect MIME from magic bytes. Office ZIP types use the declared extension."""
    if header.startswith(b"%PDF"):
        return "application/pdf"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    if header.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        if extension == ".xlsx":
            return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if extension == ".docx":
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        return "application/zip"
    if header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        if extension == ".xls":
            return "application/vnd.ms-excel"
        return "application/msword"
    return ""


def resolve_stored_upload_path(file_path: str) -> Optional[Path]:
    """Resolve a stored relative or absolute upload path under UPLOAD_DIR."""
    raw = (file_path or "").strip()
    if not raw:
        return None
    candidate = Path(raw)
    if not candidate.is_absolute():
        rel = raw.replace("\\", "/").lstrip("/")
        if rel.startswith("uploads/"):
            rel = rel[len("uploads/") :]
        candidate = UPLOAD_DIR / rel
    try:
        path = candidate.resolve()
    except OSError:
        return None
    upload_root = UPLOAD_DIR.resolve()
    if not str(path).startswith(str(upload_root)) or not path.is_file():
        return None
    return path


def reject_if_content_length_too_large(
    content_length: Optional[str],
    *,
    max_bytes: Optional[int] = None,
) -> None:
    """Reject oversized requests early using Content-Length (multipart overhead allowed)."""
    if not content_length:
        return
    try:
        length = int(content_length)
    except ValueError:
        return
    limit = max_bytes if max_bytes is not None else max_upload_bytes()
    if length > limit + CHUNK_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File exceeds the {limit} byte limit.",
        )


def _normalize_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def _validate_extension(
    filename: str,
    allowed: Optional[set[str]] = None,
) -> str:
    extension = _normalize_extension(filename)
    allowed_set = allowed if allowed is not None else ALLOWED_EXTENSIONS
    if extension not in allowed_set:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type.",
        )
    return extension


def _validate_declared_mime(content_type: Optional[str], extension: str) -> None:
    declared = (content_type or "").split(";")[0].strip().lower()
    if declared in _GENERIC_DECLARED_MIMES:
        return
    allowed = _EXT_TO_MIMES.get(extension)
    if not allowed or declared not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File MIME type does not match the file extension.",
        )


def _validate_magic(header: bytes, extension: str) -> str:
    sniffed = sniff_content_type(header, extension)
    if extension == ".csv":
        if sniffed in _BINARY_SNIFFED_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content does not match the file type.",
            )
        return "text/csv"
    allowed = _EXT_TO_MIMES.get(extension)
    if not allowed or sniffed not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match the file type.",
        )
    return sniffed


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


def _unlink_quietly(*paths: Path) -> None:
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to remove incomplete upload %s", path)


async def _close_upload(upload_file: UploadFile) -> None:
    close = getattr(upload_file, "close", None)
    if close is None:
        return
    try:
        result = close()
        if hasattr(result, "__await__"):
            await result
    except Exception:
        logger.debug("Upload file close failed", exc_info=True)


async def _read_upload_chunk(upload_file: UploadFile, chunk_size: int) -> bytes:
    chunk = await upload_file.read(chunk_size)
    return chunk or b""


async def _stream_upload_to_temp(
    upload_file: UploadFile,
    part_path: Path,
    *,
    max_bytes: int,
    extension: str,
) -> tuple[int, str]:
    """Write chunks to a .part file; return (size, sniffed_content_type)."""
    total = 0
    sniffed = ""
    async with aiofiles.open(part_path, "wb") as output:
        while True:
            chunk = await _read_upload_chunk(upload_file, CHUNK_SIZE)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=f"File exceeds the {max_bytes} byte limit.",
                )
            if not sniffed:
                sniffed = _validate_magic(chunk[:64], extension)
            await output.write(chunk)
        await output.flush()
    if total == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )
    return total, sniffed


async def _write_upload_to_path(
    upload_file: UploadFile,
    dest_path: Path,
    *,
    max_bytes: int,
    extension: str,
    timeout_seconds: float,
) -> tuple[int, str]:
    """Stream to a temp file, then atomically replace into dest_path."""
    part_path = dest_path.with_name(f"{dest_path.name}.part")
    _unlink_quietly(part_path, dest_path)
    try:
        size_bytes, sniffed = await asyncio.wait_for(
            _stream_upload_to_temp(
                upload_file,
                part_path,
                max_bytes=max_bytes,
                extension=extension,
            ),
            timeout=timeout_seconds,
        )
        os.replace(part_path, dest_path)
        return size_bytes, sniffed
    except asyncio.TimeoutError as exc:
        _unlink_quietly(part_path, dest_path)
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="Upload timed out. Please try again.",
        ) from exc
    except HTTPException:
        _unlink_quietly(part_path, dest_path)
        raise
    except OSError as exc:
        _unlink_quietly(part_path, dest_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {exc}",
        ) from exc
    except Exception:
        _unlink_quietly(part_path, dest_path)
        raise


def schedule_post_upload_work(file_path: str, size_bytes: int) -> None:
    """Enqueue non-blocking post-upload work. Never fail the HTTP response."""
    try:
        from app.tasks.file_upload import finalize_uploaded_file

        finalize_uploaded_file.delay(file_path, size_bytes)
    except Exception:
        logger.warning(
            "Could not enqueue post-upload task for %s (%s bytes)",
            file_path,
            size_bytes,
            exc_info=True,
        )


async def save_upload(file: UploadFile) -> dict:
    """Stream an upload into UPLOAD_DIR with a unique `{uuid}{ext}` name.

    Returns the recommended payload (original_filename, stored_filename, size)
    plus the existing module-upload keys so callers can stay compatible.
    """
    original_name = _validate_upload_file(file)
    extension = _validate_extension(original_name)
    _validate_declared_mime(file.content_type, extension)
    stored_name = f"{uuid.uuid4().hex}{extension}"
    ensure_uploads_dir()
    dest_path = UPLOAD_DIR / stored_name
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        size_bytes, sniffed = await _write_upload_to_path(
            file,
            dest_path,
            max_bytes=max_upload_bytes(),
            extension=extension,
            timeout_seconds=upload_timeout_seconds(),
        )
    finally:
        await _close_upload(file)

    file_path = f"uploads/{stored_name}"
    return {
        "original_filename": original_name,
        "stored_filename": stored_name,
        "size": size_bytes,
        "file_path": file_path,
        "filename": stored_name,
        "size_bytes": size_bytes,
        "content_type": sniffed or file.content_type,
    }


async def save_module_upload(
    upload_file: UploadFile,
    module_folder: str,
    *,
    name_override: Optional[str] = None,
    max_bytes: Optional[int] = None,
    allowed_extensions: Optional[set[str]] = None,
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
    extension = _validate_extension(
        name_override or original_name, allowed=allowed_extensions
    )
    _validate_declared_mime(upload_file.content_type, extension)
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
    try:
        size_bytes, sniffed = await _write_upload_to_path(
            upload_file,
            dest_path,
            max_bytes=limit,
            extension=extension,
            timeout_seconds=upload_timeout_seconds(),
        )
    finally:
        await _close_upload(upload_file)

    relative = f"{module_folder}/{storage_name}"
    return {
        "file_path": f"uploads/{relative}",
        "filename": storage_name,
        "size_bytes": size_bytes,
        "content_type": sniffed or upload_file.content_type,
        "original_filename": original_name,
        "stored_filename": storage_name,
        "size": size_bytes,
    }


async def save_upload_to_exact_path(
    upload_file: UploadFile,
    dest_path: Path,
    *,
    max_bytes: Optional[int] = None,
    allowed_extensions: Optional[set[str]] = None,
) -> int:
    """Stream an upload to a caller-chosen path (e.g. ATL import temp files)."""
    limit = max_bytes if max_bytes is not None else max_upload_bytes()
    original_name = _validate_upload_file(upload_file)
    extension = _validate_extension(original_name, allowed=allowed_extensions)
    _validate_declared_mime(upload_file.content_type, extension)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        size_bytes, _sniffed = await _write_upload_to_path(
            upload_file,
            dest_path,
            max_bytes=limit,
            extension=extension,
            timeout_seconds=upload_timeout_seconds(),
        )
        return size_bytes
    finally:
        await _close_upload(upload_file)


async def persist_optional_upload(
    upload_file: Optional[UploadFile],
    module_folder: str,
    *,
    name_override: Optional[str] = None,
    path_style: str = "uploads",
) -> Optional[str]:
    """Stream an optional multipart file; return stored relative path or None.

    path_style:
      - "uploads" (default): uploads/{module}/{filename} — existing module APIs
      - "module": {module}/{filename} — ATL white_atl/dfp download paths
    """
    if not upload_file or not getattr(upload_file, "filename", None):
        return None
    if not getattr(upload_file, "read", None):
        return None
    result = await save_module_upload(
        upload_file,
        module_folder,
        name_override=name_override,
    )
    if path_style == "module":
        return f"{module_folder}/{result['filename']}"
    return result["file_path"]
