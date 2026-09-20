import asyncio
import io
import uuid
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.services.file_upload_service import (
    build_storage_filename,
    is_safe_module_folder,
    persist_optional_upload,
    save_module_upload,
    save_upload,
    sanitize_filename,
)

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n"
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 16
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8


def _upload(filename: str, content: bytes, content_type: Optional[str] = None) -> UploadFile:
    headers = Headers({"content-type": content_type}) if content_type else None
    return UploadFile(filename=filename, file=io.BytesIO(content), headers=headers)


def test_sanitize_filename_strips_path_traversal():
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("folder\\file.pdf") == "file.pdf"


def test_build_storage_filename_uses_uuid_prefix():
    name = build_storage_filename("report.pdf")
    prefix, rest = name.split("_", 1)
    uuid.UUID(hex=prefix)
    assert rest == "report.pdf"


def test_is_safe_module_folder():
    assert is_safe_module_folder("white_atl")
    assert not is_safe_module_folder("../bad")
    assert not is_safe_module_folder("")


@pytest.mark.asyncio
async def test_save_module_upload_rejects_empty_file(tmp_path):
    with patch("app.services.file_upload_service.UPLOAD_DIR", tmp_path):
        upload = _upload("empty.pdf", b"")
        with pytest.raises(HTTPException) as exc:
            await save_module_upload(upload, "test_module")
        assert exc.value.status_code == 400
        leftover = [p for p in tmp_path.rglob("*") if p.is_file()]
        assert leftover == []


@pytest.mark.asyncio
async def test_save_module_upload_writes_uuid_file(tmp_path):
    with patch("app.services.file_upload_service.UPLOAD_DIR", tmp_path):
        upload = _upload("doc.pdf", PDF_BYTES)
        result = await save_module_upload(upload, "test_module")
        assert result["size_bytes"] == len(PDF_BYTES)
        assert result["size"] == len(PDF_BYTES)
        assert result["original_filename"] == "doc.pdf"
        assert result["file_path"].startswith("uploads/test_module/")
        stored = Path(tmp_path) / "test_module" / result["filename"]
        assert stored.is_file()
        assert stored.read_bytes() == PDF_BYTES
        assert not list(tmp_path.rglob("*.part"))


@pytest.mark.asyncio
async def test_save_module_upload_rejects_oversized_file(tmp_path):
    with patch("app.services.file_upload_service.UPLOAD_DIR", tmp_path):
        upload = _upload("big.pdf", PDF_BYTES)
        with pytest.raises(HTTPException) as exc:
            await save_module_upload(upload, "test_module", max_bytes=5)
        assert exc.value.status_code == 413
        leftover = [p for p in tmp_path.rglob("*") if p.is_file()]
        assert leftover == []


@pytest.mark.asyncio
async def test_save_module_upload_rejects_unsupported_extension(tmp_path):
    with patch("app.services.file_upload_service.UPLOAD_DIR", tmp_path):
        upload = _upload("payload.exe", b"MZ")
        with pytest.raises(HTTPException) as exc:
            await save_module_upload(upload, "test_module")
        assert exc.value.status_code == 400
        assert "Unsupported" in exc.value.detail


@pytest.mark.asyncio
async def test_save_module_upload_rejects_mime_mismatch(tmp_path):
    with patch("app.services.file_upload_service.UPLOAD_DIR", tmp_path):
        upload = _upload("doc.pdf", PDF_BYTES, content_type="image/png")
        with pytest.raises(HTTPException) as exc:
            await save_module_upload(upload, "test_module")
        assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_save_module_upload_rejects_content_mismatch(tmp_path):
    with patch("app.services.file_upload_service.UPLOAD_DIR", tmp_path):
        upload = _upload("doc.pdf", JPEG_BYTES)
        with pytest.raises(HTTPException) as exc:
            await save_module_upload(upload, "test_module")
        assert exc.value.status_code == 400
        leftover = [p for p in tmp_path.rglob("*") if p.is_file()]
        assert leftover == []


@pytest.mark.asyncio
async def test_save_upload_unique_names_and_payload(tmp_path):
    with patch("app.services.file_upload_service.UPLOAD_DIR", tmp_path):
        first = await save_upload(_upload("a.pdf", PDF_BYTES))
        second = await save_upload(_upload("b.pdf", PDF_BYTES))
        assert first["stored_filename"] != second["stored_filename"]
        assert first["original_filename"] == "a.pdf"
        assert first["size"] == len(PDF_BYTES)
        assert first["stored_filename"].endswith(".pdf")
        assert (tmp_path / first["stored_filename"]).is_file()
        assert "_" not in Path(first["stored_filename"]).stem


@pytest.mark.asyncio
async def test_persist_optional_upload_module_path_style(tmp_path):
    with patch("app.services.file_upload_service.UPLOAD_DIR", tmp_path):
        stored = await persist_optional_upload(
            _upload("white.pdf", PDF_BYTES),
            "white_atl",
            path_style="module",
        )
        assert stored is not None
        assert stored.startswith("white_atl/")
        assert not stored.startswith("uploads/")


@pytest.mark.asyncio
async def test_upload_timeout_deletes_incomplete_file(tmp_path):
    with patch("app.services.file_upload_service.UPLOAD_DIR", tmp_path), patch(
        "app.services.file_upload_service.asyncio.wait_for",
        new=AsyncMock(side_effect=asyncio.TimeoutError()),
    ):
        upload = _upload("doc.pdf", PDF_BYTES)
        with pytest.raises(HTTPException) as exc:
            await save_module_upload(upload, "test_module")
        assert exc.value.status_code == 408
        leftover = [p for p in tmp_path.rglob("*") if p.is_file()]
        assert leftover == []
