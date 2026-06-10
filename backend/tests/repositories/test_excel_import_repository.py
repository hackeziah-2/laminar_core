"""Repository tests for Excel import persistence."""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aircraft import Aircraft
from app.schemas.aircraft_schema import AircraftImportSchema
from app.repository.excel_import import (
    find_by_unique_fields,
    normalize_unique_fields,
    upsert_validated_row,
)
from app.services.excel_import.hooks.aircraft import AircraftImportHook


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("engine_tsn", "UNK", 0.0),
        ("engine_tsn", "unk", 0.0),
        ("engine_tsn", "", 0.0),
        ("engine_tsn", 2500.5, 2500.5),
        ("propeller_tsn", "UNK", 0.0),
        ("propeller_tsn", "", 0.0),
        ("propeller_tsn", None, 0.0),
    ],
)
def test_aircraft_import_schema_normalizes_unk_tsn(field, value, expected):
    validated = _validated(**{field: value})
    assert getattr(validated, field) == expected


def _validated(**overrides) -> AircraftImportSchema:
    data = {
        "registration": "REPO-001",
        "model": "172",
        "msn": "REPO-MSN-001",
        "base": "Base",
        "ownership": "Owner",
        "status": "Active",
    }
    data.update(overrides)
    return AircraftImportSchema(**data)


@pytest.mark.asyncio
async def test_upsert_inserts_then_updates(db_session: AsyncSession):
    """1. Success + 6. upsert — second call updates same unique key."""
    fields = normalize_unique_fields(["registration", "msn"])
    hook = AircraftImportHook()
    validated = _validated()

    obj, created = await upsert_validated_row(
        db_session, Aircraft, validated, fields, hook
    )
    assert created is True
    await db_session.commit()

    validated2 = _validated(model="182")
    obj2, created2 = await upsert_validated_row(
        db_session, Aircraft, validated2, fields, hook
    )
    assert created2 is False
    assert obj2.id == obj.id
    assert obj2.model == "182"


@pytest.mark.asyncio
async def test_find_by_unique_fields_not_found(db_session: AsyncSession):
    """3. Not found — lookup returns None."""
    fields = normalize_unique_fields(["registration", "msn"])
    validated = _validated(registration="MISSING-999", msn="MISSING-MSN")
    found = await find_by_unique_fields(db_session, Aircraft, validated, fields)
    assert found is None


@pytest.mark.asyncio
async def test_upsert_restores_soft_deleted_row(db_session: AsyncSession):
    """7. Soft delete — import upsert clears is_deleted."""
    fields = normalize_unique_fields(["registration", "msn"])
    hook = AircraftImportHook()
    validated = _validated(registration="SOFT-001", msn="SOFT-MSN-001")

    obj, _ = await upsert_validated_row(
        db_session, Aircraft, validated, fields, hook
    )
    await db_session.commit()

    obj.is_deleted = True
    db_session.add(obj)
    await db_session.commit()

    obj2, created = await upsert_validated_row(
        db_session, Aircraft, validated, fields, hook
    )
    assert created is False
    assert obj2.is_deleted is False

    refreshed = (
        await db_session.execute(
            select(Aircraft).where(Aircraft.registration == "SOFT-001")
        )
    ).scalar_one()
    assert refreshed.is_deleted is False
