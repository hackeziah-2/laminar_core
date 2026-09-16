"""Shared list pagination: page size 50/100/500, DB offset, and paged payload shape."""
from dataclasses import dataclass
from math import ceil
from typing import Any, Optional, Sequence, Tuple

from fastapi import HTTPException, Query, status

PAGE_SIZE_OPTIONS: Tuple[int, ...] = (50, 100, 500)
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500


@dataclass(frozen=True)
class Pagination:
    """Resolved page and page_size for LIMIT/OFFSET list queries."""

    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


def page_count(total: int, page_size: int) -> int:
    """pages = ceil(total / page_size); 0 when there are no records."""
    if total <= 0 or page_size <= 0:
        return 0
    return ceil(total / page_size)


def resolve_page_size(
    page_size: Optional[int] = None,
    limit: Optional[int] = None,
) -> int:
    """Default 50; only 50, 100, and 500 are allowed; maximum is 500."""
    if page_size is not None:
        value = page_size
    elif limit is not None:
        value = limit
    else:
        value = DEFAULT_PAGE_SIZE

    if value not in PAGE_SIZE_OPTIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="page_size must be one of 50, 100, or 500",
        )
    return value


def pagination_params(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: Optional[int] = Query(
        None,
        description="Rows per page: 50, 100, or 500. Default 50.",
    ),
    limit: Optional[int] = Query(
        None,
        description="Alias for page_size (50, 100, or 500).",
        include_in_schema=False,
    ),
) -> Pagination:
    """FastAPI dependency: page, page_size, and OFFSET for the database query."""
    return Pagination(page=page, page_size=resolve_page_size(page_size, limit))


def paged_payload(
    items: Sequence[Any],
    *,
    total: int,
    page: int,
    page_size: int,
) -> dict:
    """Standard list envelope: items, total, page, page_size, pages."""
    size = int(page_size)
    return {
        "items": list(items) if items is not None else [],
        "total": int(total or 0),
        "page": int(page),
        "page_size": size,
        "pages": page_count(int(total or 0), size),
    }
