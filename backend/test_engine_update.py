import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal, engine
from app.repository.logbooks import create_engine_logbook, update_engine_logbook
from app.schemas.logbook_schema import EngineLogbookCreate, EngineLogbookUpdate, ComponentRecordCreate
from app.models.logbooks import EngineLogbook, EngineComponentRecord
from datetime import date
from sqlalchemy.orm import selectinload

async def test():
    async with AsyncSessionLocal() as session:
        # Create
        data = EngineLogbookCreate(
            aircraft_fk=1,
            date=date.today(),
            sequence_no="ENG-TEST-123",
            componentParts=[
                ComponentRecordCreate(qty=1.0, unit="EA", nomenclature="Spark Plug", removedPartNo="1", removedSerialNo="A", installedPartNo="2", installedSerialNo="B", ataChapter="23")
            ],
            description="Test logic"
        )
        try:
            logbook = await create_engine_logbook(session, data, audit_account_id=1)
            print("Create ID:", logbook.id, "Parts:", len(logbook.component_parts))
            if not logbook.component_parts:
                print("BUG IN CREATE!")
                return
            part_id = logbook.component_parts[0].id
            print("Part created ID:", part_id)

            # Let's test providing an update payload
            # 1. Update the existing part
            # 2. Add a new part
            # 3. Another old part to delete? (We only have 1, so if not provided it's deleted)
            
            update_data = EngineLogbookUpdate(
                componentParts=[
                    ComponentRecordCreate(id=part_id, qty=2.0, unit="EA", nomenclature="Spark Plug Updated", removedPartNo="1", removedSerialNo="A", installedPartNo="2", installedSerialNo="B", ataChapter="23"),
                    ComponentRecordCreate(id=0, qty=1.0, unit="EA", nomenclature="New Part", removedPartNo="1", removedSerialNo="A", installedPartNo="2", installedSerialNo="B", ataChapter="23")
                ]
            )
            updated = await update_engine_logbook(session, logbook.id, update_data, audit_account_id=1)
            print("Update ID:", updated.id, "Parts:", len(updated.component_parts))
            for p in updated.component_parts:
                print(f"- id: {p.id}, name: {p.nomenclature}")
                
            # verify the DB directly
            db_parts = (await session.execute(select(EngineComponentRecord).where(EngineComponentRecord.engine_log_fk == updated.id))).scalars().all()
            print("DB PARTS COUNT:", len(db_parts))
            
        except Exception as e:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    import os
    # Connect directly to docker
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:5432/laminar_database"
    asyncio.run(test())
