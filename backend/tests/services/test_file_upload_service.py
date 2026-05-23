import io
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException, UploadFile

from app.services.file_upload_service import (
    build_storage_filename,
    is_safe_module_folder,
    save_module_upload,
    sanitize_filename,
)


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
        upload = UploadFile(filename="empty.txt", file=io.BytesIO(b""))
        with pytest.raises(HTTPException) as exc:
            await save_module_upload(upload, "test_module")
        assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_save_module_upload_writes_uuid_file(tmp_path):
    with patch("app.services.file_upload_service.UPLOAD_DIR", tmp_path):
        content = b"hello"
        upload = UploadFile(filename="doc.pdf", file=io.BytesIO(content))
        result = await save_module_upload(upload, "test_module")
        assert result["size_bytes"] == len(content)
        assert result["file_path"].startswith("uploads/test_module/")
        stored = Path(tmp_path) / "test_module" / result["filename"]
        assert stored.is_file()
        assert stored.read_bytes() == content


@pytest.mark.asyncio
async def test_save_module_upload_rejects_oversized_file(tmp_path):
    with patch("app.services.file_upload_service.UPLOAD_DIR", tmp_path):
        upload = UploadFile(filename="big.bin", file=io.BytesIO(b"x" * 10))
        with pytest.raises(HTTPException) as exc:
            await save_module_upload(upload, "test_module", max_bytes=5)
        assert exc.value.status_code == 413
