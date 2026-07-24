"""Shared validation helpers for persistent display_order reorder APIs."""

from __future__ import annotations

from typing import List, Sequence, Tuple

from fastapi import HTTPException, status


def validate_reorder_items(
    items: Sequence,
    *,
    id_attr: str = "id",
) -> List[Tuple[int, int]]:
    """
    Validate reorder payload items.

    Returns list of (id, display_order) preserving request order.
    Raises HTTPException on duplicate IDs, invalid/duplicate orders, or
    non-sequential display_order values (must be 1..N).

    ``id_attr`` selects the identifier field (e.g. ``"id"`` or ``"aircraft_id"``).
    """
    if not items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="items must not be empty",
        )

    ids = [getattr(item, id_attr) for item in items]
    if len(ids) != len(set(ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate record IDs are not allowed",
        )

    orders = [item.display_order for item in items]
    if any(order is None or not isinstance(order, int) or order < 1 for order in orders):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="display_order must be a positive integer starting at 1",
        )
    if len(orders) != len(set(orders)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate display_order values are not allowed",
        )

    expected = list(range(1, len(items) + 1))
    if sorted(orders) != expected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "display_order values must start at 1 and remain sequential "
                f"(expected {expected})"
            ),
        )

    return [(getattr(item, id_attr), item.display_order) for item in items]
