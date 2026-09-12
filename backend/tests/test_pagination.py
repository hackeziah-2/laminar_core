"""Unit tests for shared list pagination helpers."""
import pytest
from fastapi import HTTPException

from app.api.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    PAGE_SIZE_OPTIONS,
    page_count,
    paged_payload,
    resolve_page_size,
)


def test_page_count_uses_ceil():
    assert page_count(2500, 50) == 50
    assert page_count(51, 50) == 2
    assert page_count(50, 50) == 1
    assert page_count(0, 50) == 0


def test_resolve_page_size_default_and_allowed():
    assert resolve_page_size() == DEFAULT_PAGE_SIZE
    assert resolve_page_size(None, None) == 50
    for size in PAGE_SIZE_OPTIONS:
        assert resolve_page_size(size) == size
    assert resolve_page_size(None, 500) == 500
    assert resolve_page_size(100, 500) == 100


def test_resolve_page_size_rejects_invalid_and_over_max():
    with pytest.raises(HTTPException) as not_allowed:
        resolve_page_size(10)
    assert not_allowed.value.status_code == 422
    assert "50, 100, or 500" in not_allowed.value.detail

    with pytest.raises(HTTPException) as too_large:
        resolve_page_size(MAX_PAGE_SIZE + 1)
    assert too_large.value.status_code == 422
    assert "50, 100, or 500" in too_large.value.detail


def test_paged_payload_empty_items():
    payload = paged_payload([], total=0, page=1, page_size=50)
    assert payload == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 50,
        "pages": 0,
    }


def test_paged_payload_includes_page_size_and_pages():
    payload = paged_payload(["a"], total=1250, page=1, page_size=50)
    assert payload["page_size"] == 50
    assert payload["pages"] == 25
