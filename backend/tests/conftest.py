"""Pytest configuration and shared fixtures."""
import os

# App settings load at import time; provide a dummy URL for CI/local without .env.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.pool import StaticPool

from app.database import Base, get_session
from app.main import app
from fastapi.testclient import TestClient

# Test database URL (use in-memory SQLite for unit tests, or test PostgreSQL)
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///:memory:"
)

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=StaticPool if "sqlite" in TEST_DATABASE_URL else None,
    connect_args={"check_same_thread": False} if "sqlite" in TEST_DATABASE_URL else {},
)

TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()

    # Drop all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
def client() -> TestClient:
    """Create a test client with overridden database session."""
    import asyncio
    
    # Create tables
    async def create_tables():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    asyncio.run(create_tables())

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as test_client:
        yield test_client

    # Clean up
    app.dependency_overrides.clear()
    
    # Drop tables
    async def drop_tables():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    
    asyncio.run(drop_tables())


@pytest.fixture(scope="function")
def client_with_atl_auth(client: TestClient):
    """JWT not required: stubs get_current_active_account with Maintenance Manager (sees FOR_REVIEW/APPROVED on ATL paged)."""
    import asyncio

    from app.api.deps import get_current_active_account
    from app.models.role import Role

    async def _seed_maintenance_manager_role() -> int:
        async with TestSessionLocal() as session:
            r = Role(name="Maintenance Manager", description="ATL RBAC test")
            session.add(r)
            await session.commit()
            await session.refresh(r)
            return r.id

    mm_role_id = asyncio.run(_seed_maintenance_manager_role())

    class _Stub:
        id = 999
        role_id = mm_role_id
        status = True

    async def _override_account():
        return _Stub()

    app.dependency_overrides[get_current_active_account] = _override_account
    yield client
    app.dependency_overrides.pop(get_current_active_account, None)


@pytest.fixture(scope="function")
def client_with_regulatory_compliance_auth(client: TestClient):
    """
    Bypass JWT for tests: seeds Module + RolePermission for Regulatory Compliance,
    creates an auditor account (for audit FKs on created_by/updated_by), and stubs
    get_current_active_account to that user.
    """
    import asyncio
    import uuid

    from app.api.deps import get_current_active_account
    from app.core.security import get_password_hash
    from app.models.account import AccountInformation
    from app.models.module import Module
    from app.models.personnel_compliance import PERSONNEL_COMPLIANCE_MODULE_NAME
    from app.models.role import Role
    from app.models.role_permission import RolePermission

    async def _seed() -> tuple[int, int]:
        async with TestSessionLocal() as session:
            mod = Module(name=PERSONNEL_COMPLIANCE_MODULE_NAME)
            session.add(mod)
            await session.flush()
            role = Role(name="RC Test Role", description="pytest regulatory compliance")
            session.add(role)
            await session.flush()
            session.add(
                RolePermission(
                    role_id=role.id,
                    module_id=mod.id,
                    can_read=True,
                    can_create=True,
                    can_update=True,
                    can_delete=True,
                )
            )
            username = f"rc_audit_{uuid.uuid4().hex[:12]}"
            auditor = AccountInformation(
                first_name="Audit",
                last_name="User",
                username=username,
                password=get_password_hash("pytestauditpass123"),
                status=True,
                role_id=role.id,
            )
            session.add(auditor)
            await session.commit()
            await session.refresh(auditor)
            return auditor.id, role.id

    auditor_id, role_id = asyncio.run(_seed())

    class _Stub:
        def __init__(self, account_id: int, rid: int) -> None:
            self.id = account_id
            self.role_id = rid
            self.status = True

    async def _override_account():
        return _Stub(auditor_id, role_id)

    app.dependency_overrides[get_current_active_account] = _override_account
    yield client
    app.dependency_overrides.pop(get_current_active_account, None)


@pytest.fixture(scope="function")
def test_aircraft_data():
    """Sample aircraft data for testing."""
    return {
        "registration": "TEST-001",
        "manufacturer": "Boeing",
        "type": "Commercial",
        "model": "737-800",
        "msn": "TEST-MSN-001",
        "base": "Test Base",
        "ownership": "Test Owner",
        "status": "Active",
    }


@pytest.fixture(scope="function")
def aircraft_id(client: TestClient, test_aircraft_data: dict) -> int:
    """Create an aircraft and return its ID for use in logbook tests."""
    import json
    json_data = json.dumps(test_aircraft_data)
    response = client.post(
        "/api/v1/aircraft/",
        data={"json_data": json_data},
        files={}
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


@pytest.fixture(scope="function")
def test_aircraft_technical_log_data():
    """Sample aircraft technical log data for testing."""
    return {
        "aircraft_fk": 1,
        "sequence_no": "ATL-001",
        "nature_of_flight": "TR",
        "origin_station": "TEST-ORG",
        "origin_date": "2025-01-17",
        "origin_time": "10:00:00",
        "destination_station": "TEST-DEST",
        "destination_date": "2025-01-17",
        "destination_time": "12:00:00",
        "number_of_landings": 1,
        "hobbs_meter_start": 100.0,
        "hobbs_meter_end": 102.5,
        "hobbs_meter_total": 2.5,
        "tachometer_start": 100.0,
        "tachometer_end": 102.5,
        "tachometer_total": 2.5,
        "component_parts": [],
    }
