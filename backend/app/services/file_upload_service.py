"""Streamed file uploads: chunked I/O, size/type checks, unique names, fail-safe cleanup."""
from __future__ import annotations

import asyncio
import logging
import math
import re
import codecs
from functools import wraps
import hashlib
import tempfile
import threading
import time
import weakref
import zipfile
import struct
from xml.etree import ElementTree
import os
import uuid
from pathlib import Path
from typing import Optional

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
    return value if math.isfinite(value) and value > 0 else DEFAULT_UPLOAD_TIMEOUT_SECONDS


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
    suffix = Path(safe).suffix
    stem = safe[:-len(suffix)] if suffix else safe
    return (stem.encode("utf-8")[:160].decode("utf-8", errors="ignore") or "upload") + suffix[:20]


def build_storage_filename(original_name: str, *, name_override: Optional[str] = None) -> str:
    """Return `{uuid}_{sanitized_base}` so stored files are unique and non-guessable."""
    base = sanitize_filename(name_override or original_name or "upload")
    return f"{uuid.uuid4().hex}_{base}"


def sniff_content_type(header: bytes, extension: str) -> str:
    """Detect MIME from magic bytes. Office ZIP types use the declared extension."""
    if header.startswith(b"%PDF-"):
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
    if not path.is_relative_to(upload_root) or not path.is_file():
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
    if len(original.encode("utf-8")) > 1024 or any(ord(c) < 32 for c in original):
        raise HTTPException(status_code=400, detail="Invalid filename")
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


_copy_slots = weakref.WeakKeyDictionary()


def _slots() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    if loop not in _copy_slots:
        _copy_slots[loop] = asyncio.Semaphore(4)
    return _copy_slots[loop]


def _validate_container(path: Path, extension: str, tail: bytes) -> None:
    """Bounded structural checks; not malware scanning or full document rendering."""
    invalid = HTTPException(status_code=400, detail="File is corrupted or incomplete.")
    if extension == ".pdf":
        match = re.search(rb"startxref\s+(\d+)\s+%%EOF\s*$", tail)
        if not match:
            raise invalid
        offset = int(match.group(1))
        if offset <= 0 or offset >= path.stat().st_size:
            raise invalid
        with path.open("rb") as source:
            source.seek(offset)
            xref = source.read(4096)
        if not xref.startswith(b"xref") and not (
            re.match(rb"\d+\s+\d+\s+obj\b", xref) and re.search(rb"/Type\s*/XRef", xref)
        ):
            raise invalid
    elif extension in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        from PIL import Image
        try:
            with Image.open(path) as image:
                if image.width * image.height > 40_000_000:
                    raise invalid
                image.verify()
            if extension in {".jpg", ".jpeg"} and not tail.rstrip().endswith(b"\xff\xd9"):
                raise invalid
        except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
            raise invalid from exc
    elif extension in {".docx", ".xlsx"}:
        # Reject ZIP64/massive directories before ZipFile allocates entries.
        with path.open("rb") as source:
            source.seek(max(0, path.stat().st_size - 65557))
            end = source.read(65557)
        marker = end.rfind(b"PK\x05\x06")
        if marker < 0 or len(end) - marker < 22:
            raise invalid
        count = struct.unpack_from("<H", end, marker + 10)[0]
        if count > 4096:
            raise invalid
        try:
            with zipfile.ZipFile(path) as archive:
                entries = archive.infolist()
                names = {entry.filename for entry in entries}
                required = "word/document.xml" if extension == ".docx" else "xl/workbook.xml"
                if not {"[Content_Types].xml", required}.issubset(names):
                    raise invalid
                if len(entries) > 4096 or sum(e.file_size for e in entries) > 100 * 1024 * 1024:
                    raise invalid
                for entry in entries:
                    if entry.flag_bits & 1 or entry.file_size > max(1, entry.compress_size) * 200:
                        raise invalid
                # Check core XML + CRC, without expanding every embedded object.
                for name in ["[Content_Types].xml", required]:
                    if archive.getinfo(name).file_size > 1024 * 1024:
                        raise invalid
                    data = archive.read(name)
                    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
                        raise invalid
                    ElementTree.fromstring(data)
        except (OSError, ValueError, zipfile.BadZipFile, ElementTree.ParseError, RuntimeError) as exc:
            raise invalid from exc
    elif extension in {".doc", ".xls"}:
        import olefile
        try:
            with olefile.OleFileIO(path) as document:
                expected = ["WordDocument"] if extension == ".doc" else ["Workbook", "Book"]
                if not any(document.exists(name) for name in expected):
                    raise invalid
        except (OSError, ValueError) as exc:
            raise invalid from exc


def _copy_upload(source, dest_path: Path, max_bytes: int, extension: str,
                 stop: threading.Event, published: threading.Event, deadline: float):
    """One worker owns the source, copy, hash, validation and atomic publication."""
    fd, temporary = tempfile.mkstemp(prefix=".upload-", suffix=".part", dir=dest_path.parent)
    part_path = Path(temporary)
    digest = hashlib.sha256()
    total = 0
    tail = b""
    decoder = codecs.getincrementaldecoder("utf-8-sig")() if extension == ".csv" else None
    def check():
        if stop.is_set():
            raise InterruptedError("Upload cancelled")
        if time.monotonic() >= deadline:
            raise TimeoutError("Upload timed out")
    try:
        with os.fdopen(fd, "wb") as output:
            header = source.read(64)
            while len(header) < 64:
                more = source.read(64 - len(header))
                if not more:
                    break
                header += more
            if not header:
                raise HTTPException(status_code=400, detail="Uploaded file is empty")
            sniffed = _validate_magic(header, extension)
            chunk = header
            while chunk:
                check()
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(status_code=413, detail=f"File exceeds the {max_bytes} byte limit.")
                if decoder:
                    try:
                        if any(c in chunk for c in (b"\x00", b"\x01", b"\x02")):
                            raise UnicodeError("Binary CSV")
                        decoder.decode(chunk)
                    except UnicodeError as exc:
                        raise HTTPException(status_code=400, detail="CSV must contain UTF-8 text.") from exc
                digest.update(chunk)
                output.write(chunk)
                tail = chunk[-1024:] if len(chunk) >= 1024 else (tail + chunk)[-1024:]
                chunk = source.read(min(CHUNK_SIZE, max_bytes - total + 1))
            if decoder:
                try:
                    decoder.decode(b"", final=True)
                except UnicodeError as exc:
                    raise HTTPException(status_code=400, detail="CSV must contain UTF-8 text.") from exc
            output.flush()
        check()
        _validate_container(part_path, extension, tail)
        with part_path.open("rb") as durable:
            os.fsync(durable.fileno())
        check()
        # link is atomic and fails on collision; never delete/overwrite an existing file.
        os.link(part_path, dest_path)
        published.set()
        directory = os.open(dest_path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return total, sniffed, digest.hexdigest()
    finally:
        part_path.unlink(missing_ok=True)


async def _write_upload_to_path(
    upload_file: UploadFile, dest_path: Path, *, max_bytes: int,
    extension: str, timeout_seconds: float,
) -> tuple[int, str, str]:
    known_size = getattr(upload_file, "size", None)
    if known_size is not None and known_size > max_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds the {max_bytes} byte limit.")
    stop, published = threading.Event(), threading.Event()
    async with _slots():
        job = asyncio.create_task(asyncio.to_thread(
            _copy_upload, upload_file.file, dest_path, max_bytes, extension,
            stop, published, time.monotonic() + timeout_seconds,
        ))
        try:
            return await asyncio.wait_for(asyncio.shield(job), timeout_seconds)
        except BaseException as exc:
            stop.set()
            # A thread cannot be cancelled: drain it before closing its input or unlinking.
            while not job.done():
                try:
                    await asyncio.shield(job)
                except asyncio.CancelledError:
                    continue
                except BaseException:
                    break
            try:
                job.result()
            except BaseException:
                pass
            if published.is_set():
                _unlink_quietly(dest_path)
            if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
                raise HTTPException(status_code=408, detail="Upload timed out. Please try again.") from exc
            if isinstance(exc, FileExistsError):
                raise HTTPException(status_code=409, detail="Upload destination already exists.") from exc
            if isinstance(exc, OSError):
                logger.exception("Failed to store upload")
                raise HTTPException(status_code=500, detail="Failed to save file.") from exc
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


def _close_after_call(function):
    @wraps(function)
    async def wrapped(*args, **kwargs):
        file = args[0] if args else kwargs.get("file", kwargs.get("upload_file"))
        try:
            return await function(*args, **kwargs)
        finally:
            await _close_upload(file)
    return wrapped


@_close_after_call
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
        size_bytes, sniffed, checksum = await _write_upload_to_path(
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


@_close_after_call
async def save_module_upload(
    upload_file: UploadFile,
    module_folder: str,
    *,
    name_override: Optional[str] = None,
    max_bytes: Optional[int] = None,
    allowed_extensions: Optional[set[str]] = None,
    include_checksum: bool = False,
    track_pending: bool = False,
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
    extension = _validate_extension(original_name, allowed=allowed_extensions)
    if name_override and _validate_extension(name_override, allowed_extensions) != extension:
        raise HTTPException(status_code=400, detail="Filename override must preserve the extension.")
    _validate_declared_mime(upload_file.content_type, extension)
    storage_name = build_storage_filename(original_name, name_override=name_override)

    ensure_uploads_dir()
    target_dir = (UPLOAD_DIR / module_folder).resolve()
    if not target_dir.is_relative_to(UPLOAD_DIR.resolve()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid upload destination",
        )
    target_dir.mkdir(parents=True, exist_ok=True)

    dest_path = target_dir / storage_name
    pending = dest_path.with_name(dest_path.name + ".pending")
    if track_pending:
        pending.touch(exist_ok=False)
    try:
        size_bytes, sniffed, checksum = await _write_upload_to_path(
            upload_file,
            dest_path,
            max_bytes=limit,
            extension=extension,
            timeout_seconds=upload_timeout_seconds(),
        )
    except BaseException:
        if track_pending:
            _unlink_quietly(pending)
        raise
    finally:
        await _close_upload(upload_file)

    relative = f"{module_folder}/{storage_name}"
    return {
        **({"sha256": checksum} if include_checksum else {}),
        "file_path": f"uploads/{relative}",
        "filename": storage_name,
        "size_bytes": size_bytes,
        "content_type": sniffed or upload_file.content_type,
        "original_filename": original_name,
        "stored_filename": storage_name,
        "size": size_bytes,
    }


@_close_after_call
async def save_upload_to_exact_path(
    upload_file: UploadFile,
    dest_path: Path,
    *,
    max_bytes: Optional[int] = None,
    allowed_extensions: Optional[set[str]] = None,
    track_pending: bool = False,
) -> int:
    """Stream an upload to a caller-chosen path (e.g. ATL import temp files)."""
    limit = max_bytes if max_bytes is not None else max_upload_bytes()
    original_name = _validate_upload_file(upload_file)
    extension = _validate_extension(original_name, allowed=allowed_extensions)
    _validate_declared_mime(upload_file.content_type, extension)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    pending = dest_path.with_name(dest_path.name + ".pending")
    if track_pending:
        pending.touch(exist_ok=False)
    try:
        size_bytes, _sniffed, _checksum = await _write_upload_to_path(
            upload_file,
            dest_path,
            max_bytes=limit,
            extension=extension,
            timeout_seconds=upload_timeout_seconds(),
        )
        return size_bytes
    except BaseException:
        if track_pending:
            _unlink_quietly(pending)
        raise
    finally:
        await _close_upload(upload_file)


async def persist_optional_upload(
    upload_file: Optional[UploadFile],
    module_folder: str,
    *,
    name_override: Optional[str] = None,
    path_style: str = "uploads",
    session=None,
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
    from app.services.upload_transaction import release_upload_reads
    async with release_upload_reads(session):
        result = await save_module_upload(
            upload_file,
            module_folder,
            name_override=name_override,
            track_pending=session is not None,
        )
    if session is not None:
        from app.services.upload_transaction import track_upload
        track_upload(session, UPLOAD_DIR / module_folder / result["filename"])
    if path_style == "module":
        return f"{module_folder}/{result['filename']}"
    return result["file_path"]
