import os
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@db:5432/laminar_database"
)

config = context.config
fileConfig(config.config_file_name)

from app.database import Base  # same Base as all models inherit
from app.models.aircraft import Aircraft
from app.models.flight import Flight
from app.models.user import User
from app.models.aircraft_logbook_entries import AircraftLogbookEntry
from app.models.aircraft_techinical_log import AircraftTechnicalLog, ComponentPartsRecord
from app.models.atl_monitoring import LDNDMonitoring
from app.models.account import AccountInformation
from app.models.logbooks import EngineLogbook, AirframeLogbook, AvionicsLogbook, PropellerLogbook
from app.models.document_on_board import DocumentOnBoard
from app.models.ad_monitoring import ADMonitoring, WorkOrderADMonitoring

target_metadata = Base.metadata

def run_migrations_offline():
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    engine = create_async_engine(DATABASE_URL, poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio
    asyncio.run(run_migrations_online())