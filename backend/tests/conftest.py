"""Pytest configuration and shared fixtures."""
import os
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
