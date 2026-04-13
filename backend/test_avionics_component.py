import asyncio
from app.database import AsyncSessionLocal, engine
from app.repository.logbooks import create_avionics_logbook, update_avionics_logbook
from app.schemas.logbook_schema import AvionicsLogbookCreate, AvionicsLogbookUpdate, ComponentRecordCreate
from datetime import date

async def test():
    async with AsyncSessionLocal() as session:
        data = AvionicsLogbookCreate(
            aircraft_fk=1,
            date=date.today(),
            sequence_no="AV-001",
            component_parts=[
                ComponentRecordCreate(
                    qty=1.0,
                    unit="EA",
                    nomenclature="Radio",
                    removedPartNo="123",
                    removedSerialNo="SN123",
                    installedPartNo="456",
                    installedSerialNo="SN456",
                    ataChapter="23"
                )
            ]
        )
        try:
            logbook = await create_avionics_logbook(session, data, audit_account_id=1)
            print("Create Response:", logbook.dict())
            
            update_data = AvionicsLogbookUpdate(
                component_parts=[
                    ComponentRecordCreate(
                        qty=2.0,
                        unit="EA",
                        nomenclature="Radio 2",
                        removedPartNo="123",
                        removedSerialNo="SN123",
                        installedPartNo="456",
                        installedSerialNo="SN456",
                        ataChapter="23"
                    )
                ]
            )
            updated = await update_avionics_logbook(session, logbook.id, update_data, audit_account_id=1)
            print("Update Response:", updated.dict())
        except Exception as e:
            print("ERROR!!!", e)

if __name__ == "__main__":
    asyncio.run(test())
