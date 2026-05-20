"""Pytest configuration and shared fixtures."""
import os

import pytest

# App settings load at import time; provide a dummy URL for CI/local without .env.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.pool import StaticPool
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.database import Base, get_session
from app.main import app
from fastapi.testclient import TestClient
from tests.factories.rbac import seed_account, seed_role


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "no_auth: API test expects no Bearer token on client")


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


async def _create_test_tables() -> None:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _drop_test_tables() -> None:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """httpx async client with test DB session override (preferred for new API tests)."""
    await _create_test_tables()

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await _drop_test_tables()


@pytest.fixture(scope="function")
def _base_client() -> Generator[TestClient, None, None]:
    """TestClient with DB override; no Authorization header."""
    import asyncio

    asyncio.run(_create_test_tables())

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    asyncio.run(_drop_test_tables())


def _seed_auth_account_id() -> int:
    """Create a role + active account for JWT-backed API tests."""
    import asyncio

    async def _seed() -> int:
        async with TestSessionLocal() as session:
            role_id = await seed_role(session)
            account_id = await seed_account(session, role_id=role_id)
            await session.commit()
            return account_id

    return asyncio.run(_seed())


@pytest.fixture(scope="function")
def client(_base_client: TestClient, request: pytest.FixtureRequest) -> TestClient:
    """TestClient; includes Bearer JWT unless the test is marked ``no_auth``."""
    if request.node.get_closest_marker("no_auth") is None:
        account_id = _seed_auth_account_id()
        token = create_access_token(
            {"sub": str(account_id), "username": "pytest_auth_user"}
        )
        _base_client.headers["Authorization"] = f"Bearer {token}"
    yield _base_client
    _base_client.headers.pop("Authorization", None)


@pytest.fixture(scope="function")
def auth_account_id(request: pytest.FixtureRequest) -> int:
    """Active account in the test DB; JWT ``sub`` must be this numeric id."""
    if request.node.get_closest_marker("no_auth") is not None:
        pytest.skip("auth_account_id is not used in no_auth tests")
    return _seed_auth_account_id()


@pytest.fixture(scope="function")
def auth_headers(auth_account_id: int) -> dict[str, str]:
    """Bearer JWT for API endpoints that require authentication."""
    token = create_access_token(
        {"sub": str(auth_account_id), "username": "pytest_auth_user"}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def authenticated_client(client: TestClient, auth_headers: dict) -> Generator[TestClient, None, None]:
    """TestClient with default Authorization header for protected routes."""
    client.headers.update(auth_headers)
    yield client
    client.headers.pop("Authorization", None)


@pytest.fixture(scope="function")
async def async_auth_headers(auth_account_id: int) -> dict[str, str]:
    """Bearer JWT for async httpx API tests."""
    token = create_access_token(
        {"sub": str(auth_account_id), "username": "pytest_auth_user"}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
async def async_authenticated_client(
    async_client: AsyncClient,
    async_auth_headers: dict,
) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient with default Authorization header."""
    async_client.headers.update(async_auth_headers)
    yield async_client
    async_client.headers.pop("Authorization", None)


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
def client_with_general_information_import_auth(client: TestClient) -> Generator[TestClient, None, None]:
    """Account with can_create on General Information (aircraft Excel import)."""
    import asyncio

    from app.api.deps import get_current_active_account
    from app.core.rbac_modules import GENERAL_INFORMATION_MODULE
    from tests.factories.rbac import seed_account_with_module_permissions

    async def _seed() -> tuple[int, int]:
        async with TestSessionLocal() as session:
            return await seed_account_with_module_permissions(
                session,
                {
                    GENERAL_INFORMATION_MODULE: {
                        "can_read": True,
                        "can_create": True,
                    },
                },
            )

    account_id, role_id = asyncio.run(_seed())

    class _Stub:
        def __init__(self, aid: int, rid: int) -> None:
            self.id = aid
            self.role_id = rid
            self.status = True

    async def _override():
        return _Stub(account_id, role_id)

    app.dependency_overrides[get_current_active_account] = _override
    yield client
    app.dependency_overrides.pop(get_current_active_account, None)


@pytest.fixture(scope="function")
def client_with_maintenance_import_auth(client: TestClient) -> Generator[TestClient, None, None]:
    """Account with can_create on Maintenance (ATL Excel import)."""
    import asyncio

    from app.api.deps import get_current_active_account
    from app.core.rbac_modules import MAINTENANCE_MODULE
    from tests.factories.rbac import seed_account_with_module_permissions

    async def _seed() -> tuple[int, int]:
        async with TestSessionLocal() as session:
            return await seed_account_with_module_permissions(
                session,
                {
                    MAINTENANCE_MODULE: {
                        "can_read": True,
                        "can_create": True,
                    },
                },
            )

    account_id, role_id = asyncio.run(_seed())

    class _Stub:
        def __init__(self, aid: int, rid: int) -> None:
            self.id = aid
            self.role_id = rid
            self.status = True

    async def _override():
        return _Stub(account_id, role_id)

    app.dependency_overrides[get_current_active_account] = _override
    yield client
    app.dependency_overrides.pop(get_current_active_account, None)


@pytest.fixture(scope="function")
def client_without_import_permission(client: TestClient) -> Generator[TestClient, None, None]:
    """Authenticated account with module present but can_create denied (expect 403)."""
    import asyncio

    from app.api.deps import get_current_active_account
    from app.core.rbac_modules import GENERAL_INFORMATION_MODULE
    from tests.factories.rbac import (
        seed_account,
        seed_module,
        seed_role,
        seed_role_permission,
    )

    async def _seed() -> tuple[int, int]:
        async with TestSessionLocal() as session:
            role_id = await seed_role(session)
            module_id = await seed_module(session, GENERAL_INFORMATION_MODULE)
            await seed_role_permission(
                session,
                role_id=role_id,
                module_id=module_id,
                can_read=True,
                can_create=False,
            )
            account_id = await seed_account(session, role_id=role_id)
            await session.commit()
            return account_id, role_id

    account_id, role_id = asyncio.run(_seed())

    class _Stub:
        def __init__(self, aid: int, rid: int) -> None:
            self.id = aid
            self.role_id = rid
            self.status = True

    async def _override():
        return _Stub(account_id, role_id)

    app.dependency_overrides[get_current_active_account] = _override
    yield client
    app.dependency_overrides.pop(get_current_active_account, None)


@pytest.fixture(scope="function")
async def async_client_with_general_information_import_auth(
    async_client: AsyncClient,
) -> AsyncGenerator[AsyncClient, None]:
    """Async client + General Information can_create (for aircraft import tests)."""
    import asyncio

    from app.api.deps import get_current_active_account
    from app.core.rbac_modules import GENERAL_INFORMATION_MODULE
    from tests.factories.rbac import seed_account_with_module_permissions

    async def _seed() -> tuple[int, int]:
        async with TestSessionLocal() as session:
            return await seed_account_with_module_permissions(
                session,
                {GENERAL_INFORMATION_MODULE: {"can_read": True, "can_create": True}},
            )

    account_id, role_id = await _seed()

    class _Stub:
        def __init__(self, aid: int, rid: int) -> None:
            self.id = aid
            self.role_id = rid
            self.status = True

    async def _override():
        return _Stub(account_id, role_id)

    app.dependency_overrides[get_current_active_account] = _override
    yield async_client
    app.dependency_overrides.pop(get_current_active_account, None)


@pytest.fixture(scope="function")
def test_aircraft_data():
    """Sample aircraft data for testing."""
    return {
        "registration": "TEST-001",
        "manufacturer": "Boeing",
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
        files={},
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
