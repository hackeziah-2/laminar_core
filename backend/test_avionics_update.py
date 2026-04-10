import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal, engine
from app.repository.logbooks import create_avionics_logbook, update_avionics_logbook
from app.schemas.logbook_schema import AvionicsLogbookCreate, AvionicsLogbookUpdate, ComponentRecordCreate
from app.models.logbooks import AvionicsLogbook, AvionicsComponentRecord
from datetime import date

async def test():
    async with AsyncSessionLocal() as session:
        # Check if we can create and update successfully
        data = AvionicsLogbookCreate(
            aircraft_fk=1,
            date=date.today(),
            sequence_no="AV-TEST-123",
            component_parts=[
                ComponentRecordCreate(qty=1.0, unit="EA", nomenclature="Radio", removedPartNo="1", removedSerialNo="A", installedPartNo="2", installedSerialNo="B", ataChapter="23")
            ]
        )
        try:
            logbook = await create_avionics_logbook(session, data, audit_account_id=1)
            print("Create ID:", logbook.id, "Parts:", len(logbook.component_parts))
            
            update_data = AvionicsLogbookUpdate(
                component_parts=[
                    ComponentRecordCreate(qty=2.0, unit="EA", nomenclature="Radio Updated", removedPartNo="1", removedSerialNo="A", installedPartNo="2", installedSerialNo="B", ataChapter="23")
                ]
            )
            updated = await update_avionics_logbook(session, logbook.id, update_data, audit_account_id=1)
            print("Update ID:", updated.id, "Parts:", len(updated.component_parts))
            print("Update Parts Content:", [x.nomenclature for x in updated.component_parts])
            
        except Exception as e:
            print("ERROR!!!", e)

if __name__ == "__main__":
    asyncio.run(test())
