import importlib.util
import os
from pathlib import Path
import uuid
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine
from alembic.migration import MigrationContext
from alembic.operations import Operations


@pytest.mark.asyncio
async def test_upgrade_downgrade(tmp_path):
    url=os.getenv('UPLOAD_TEST_DATABASE_URL')
    schema='upload_migration_'+uuid.uuid4().hex if url else None
    engine=create_async_engine(url or 'sqlite+aiosqlite:///'+str(tmp_path/'migration.db'))
    spec=importlib.util.spec_from_file_location('upload_migration',
        Path(__file__).resolve().parents[2]/'alembic/versions/i0j1k2l3m4n5_upload_assets.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    async with engine.begin() as conn:
        if schema:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            await conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        await conn.execute(text('CREATE TABLE account_information (id INTEGER PRIMARY KEY)'))
        def run(sync):
            with Operations.context(MigrationContext.configure(sync)):
                migration.upgrade()
                columns={c['name'] for c in inspect(sync).get_columns('upload_assets',schema=schema)}
                assert 'sha256' in columns and 'data' not in columns
                migration.downgrade()
                assert 'upload_assets' not in inspect(sync).get_table_names(schema=schema)
        await conn.run_sync(run)
        if schema: await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    await engine.dispose()
