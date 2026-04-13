from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.logbooks import create_engine_logbook, update_engine_logbook
from app.schemas.logbook_schema import ComponentRecordCreate, EngineLogbookCreate, EngineLogbookUpdate


@pytest.mark.asyncio
async def test_engine_logbook_create_and_update_component_parts_without_preloaded_relationship(
    db_session: AsyncSession,
):
    created = await create_engine_logbook(
        db_session,
        EngineLogbookCreate(
            aircraft_fk=1,
            date=date(2026, 4, 15),
            sequence_no="ENG-REPO-COMP-API-001",
            description="Removed damaged fuel nozzle and installed serviceable replacement.",
            component_parts=[
                ComponentRecordCreate(
                    qty=1,
                    unit="pc",
                    nomenclature="Fuel Nozzle",
                    removedPartNo="FN-900",
                    removedSerialNo="FN-OLD-7788",
                    installedPartNo="FN-901",
                    installedSerialNo="FN-NEW-8899",
                    ataChapter="73",
                )
            ],
        ),
    )

    assert created.id is not None
    assert len(created.component_parts) == 1
    part_id = created.component_parts[0].id

    updated = await update_engine_logbook(
        db_session,
        created.id,
        EngineLogbookUpdate(
            description="Updated engine work entry",
            component_parts=[
                ComponentRecordCreate(
                    id=part_id,
                    qty=1,
                    unit="pc",
                    nomenclature="Fuel Nozzle Reworked",
                    removedPartNo="FN-900",
                    removedSerialNo="FN-OLD-7788",
                    installedPartNo="FN-902",
                    installedSerialNo="FN-NEW-9900",
                    ataChapter="73",
                ),
                ComponentRecordCreate(
                    qty=1,
                    unit="pc",
                    nomenclature="Fuel Seal",
                    removedPartNo="FS-100",
                    removedSerialNo="FS-OLD-100",
                    installedPartNo="FS-101",
                    installedSerialNo="FS-NEW-101",
                    ataChapter="73",
                ),
            ],
        ),
    )

    assert updated is not None
    assert updated.description == "Updated engine work entry"
    assert len(updated.component_parts) == 2
    assert {part.nomenclature for part in updated.component_parts} == {
        "Fuel Nozzle Reworked",
        "Fuel Seal",
    }
