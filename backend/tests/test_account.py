"""Unit tests for Account Information endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import AccountInformation
from app.repository.account import (
    list_account_informations,
    create_account_information,
    get_account_information,
    update_account_information,
    soft_delete_account_information,
)
from app.schemas.account_schema import (
    AccountInformationCreate,
    AccountInformationUpdate,
)


def test_list_account_information_empty(client: TestClient):
    """Test listing account information when database is empty."""
    response = client.get("/api/v1/account-information/paged?limit=10&page=1")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["pages"] == 0
    assert len(data["items"]) == 0


def test_create_account_information(client: TestClient):
    """Test creating a new account information."""
    account_data = {
        "first_name": "John",
        "last_name": "Doe",
        "middle_name": "M",
        "username": "jdoe",
        "password": "securepassword123",
        "designation": "Pilot",
        "license_no": "LIC123456",
        "status": True,
    }
    response = client.post("/api/v1/account-information/", json=account_data)
    assert response.status_code == 201
    data = response.json()
    assert data["first_name"] == account_data["first_name"]
    assert data["last_name"] == account_data["last_name"]
    assert data["username"] == account_data["username"]
    assert data["id"] is not None
    # Password should not be in response
    assert "password" not in data


def test_create_account_information_duplicate_username(client: TestClient):
    """Test creating account information with duplicate username."""
    account_data = {
        "first_name": "John",
        "last_name": "Doe",
        "username": "jdoe",
        "password": "securepassword123",
        "status": True,
    }
    # Create first account
    response1 = client.post("/api/v1/account-information/", json=account_data)
    assert response1.status_code == 201

    # Try to create duplicate
    response2 = client.post("/api/v1/account-information/", json=account_data)
    assert response2.status_code == 400
    assert "already exists" in response2.json()["detail"].lower()


def test_get_account_information(client: TestClient):
    """Test getting a single account information by ID."""
    # Create account first
    account_data = {
        "first_name": "Jane",
        "last_name": "Smith",
        "username": "jsmith",
        "password": "securepassword123",
        "status": True,
    }
    create_response = client.post(
        "/api/v1/account-information/", json=account_data
    )
    account_id = create_response.json()["id"]

    # Get the account
    response = client.get(f"/api/v1/account-information/{account_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == account_id
    assert data["first_name"] == account_data["first_name"]
    assert data["last_name"] == account_data["last_name"]
    assert data["username"] == account_data["username"]
    # Password should not be in response
    assert "password" not in data


def test_get_account_information_not_found(client: TestClient):
    """Test getting a non-existent account information."""
    response = client.get("/api/v1/account-information/999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_update_account_information(client: TestClient):
    """Test updating an account information."""
    # Create account first
    account_data = {
        "first_name": "John",
        "last_name": "Doe",
        "username": "jdoe_update",
        "password": "securepassword123",
        "status": True,
    }
    create_response = client.post(
        "/api/v1/account-information/", json=account_data
    )
    account_id = create_response.json()["id"]

    # Update the account
    update_data = {
        "first_name": "Johnny",
        "designation": "Senior Pilot",
        "status": False,
    }
    response = client.put(
        f"/api/v1/account-information/{account_id}", json=update_data
    )
    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == update_data["first_name"]
    assert data["designation"] == update_data["designation"]
    assert data["status"] == update_data["status"]
    # Other fields should remain unchanged
    assert data["last_name"] == account_data["last_name"]
    assert data["username"] == account_data["username"]


def test_update_account_information_password(client: TestClient):
    """Test updating account information password."""
    # Create account first
    account_data = {
        "first_name": "John",
        "last_name": "Doe",
        "username": "jdoe_pwd",
        "password": "oldpassword123",
        "status": True,
    }
    create_response = client.post(
        "/api/v1/account-information/", json=account_data
    )
    account_id = create_response.json()["id"]

    # Update password
    update_data = {"password": "newpassword456"}
    response = client.put(
        f"/api/v1/account-information/{account_id}", json=update_data
    )
    assert response.status_code == 200
    data = response.json()
    # Password should not be in response
    assert "password" not in data


def test_update_account_information_duplicate_username(client: TestClient):
    """Test updating account information with duplicate username."""
    # Create first account
    account_data1 = {
        "first_name": "John",
        "last_name": "Doe",
        "username": "jdoe1",
        "password": "securepassword123",
        "status": True,
    }
    create_response1 = client.post(
        "/api/v1/account-information/", json=account_data1
    )
    assert create_response1.status_code == 201

    # Create second account
    account_data2 = {
        "first_name": "Jane",
        "last_name": "Smith",
        "username": "jsmith1",
        "password": "securepassword123",
        "status": True,
    }
    create_response2 = client.post(
        "/api/v1/account-information/", json=account_data2
    )
    account_id2 = create_response2.json()["id"]

    # Try to update second account with first account's username
    update_data = {"username": "jdoe1"}
    response = client.put(
        f"/api/v1/account-information/{account_id2}", json=update_data
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


def test_update_account_information_not_found(client: TestClient):
    """Test updating a non-existent account information."""
    update_data = {"first_name": "Johnny"}
    response = client.put("/api/v1/account-information/999", json=update_data)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_delete_account_information(client: TestClient):
    """Test soft deleting an account information."""
    # Create account first
    account_data = {
        "first_name": "John",
        "last_name": "Doe",
        "username": "jdoe_delete",
        "password": "securepassword123",
        "status": True,
    }
    create_response = client.post(
        "/api/v1/account-information/", json=account_data
    )
    account_id = create_response.json()["id"]

    # Delete the account
    response = client.delete(f"/api/v1/account-information/{account_id}")
    assert response.status_code == 204

    # Verify it's soft deleted (should not appear in list)
    list_response = client.get(
        "/api/v1/account-information/paged?limit=10&page=1"
    )
    assert list_response.status_code == 200
    data = list_response.json()
    assert not any(item["id"] == account_id for item in data["items"])

    # Verify get returns 404
    get_response = client.get(f"/api/v1/account-information/{account_id}")
    assert get_response.status_code == 404


def test_delete_account_information_not_found(client: TestClient):
    """Test deleting a non-existent account information."""
    response = client.delete("/api/v1/account-information/999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_list_account_information_with_search(client: TestClient):
    """Test listing account information with search filter."""
    # Create multiple accounts
    accounts = [
        {
            "first_name": "John",
            "last_name": "Doe",
            "username": "jdoe_search1",
            "password": "securepassword123",
            "status": True,
        },
        {
            "first_name": "Jane",
            "last_name": "Smith",
            "username": "jsmith_search1",
            "password": "securepassword123",
            "status": True,
        },
        {
            "first_name": "Bob",
            "last_name": "Johnson",
            "username": "bjohnson_search1",
            "password": "securepassword123",
            "designation": "Pilot",
            "status": True,
        },
    ]

    for account_data in accounts:
        client.post("/api/v1/account-information/", json=account_data)

    # Search by first name
    response = client.get(
        "/api/v1/account-information/paged?search=John&limit=10&page=1"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(
        "John" in item["first_name"] or "John" in item["last_name"]
        for item in data["items"]
    )

    # Search by designation
    response = client.get(
        "/api/v1/account-information/paged?search=Pilot&limit=10&page=1"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(
        item.get("designation") == "Pilot" for item in data["items"]
    )


def test_list_account_information_pagination(client: TestClient):
    """Test account information listing pagination."""
    # Create multiple accounts
    for i in range(5):
        account_data = {
            "first_name": f"User{i}",
            "last_name": "Test",
            "username": f"user{i}_pagination",
            "password": "securepassword123",
            "status": True,
        }
        client.post("/api/v1/account-information/", json=account_data)

    # Test pagination
    response = client.get(
        "/api/v1/account-information/paged?limit=2&page=1"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 2
    assert data["page"] == 1
    assert data["total"] >= 5


def test_list_account_information_sorting(client: TestClient):
    """Test account information listing with sorting."""
    # Create multiple accounts
    accounts = [
        {
            "first_name": "Alice",
            "last_name": "Adams",
            "username": "aalice_sort",
            "password": "securepassword123",
            "status": True,
        },
        {
            "first_name": "Bob",
            "last_name": "Brown",
            "username": "bbob_sort",
            "password": "securepassword123",
            "status": True,
        },
        {
            "first_name": "Charlie",
            "last_name": "Clark",
            "username": "ccharlie_sort",
            "password": "securepassword123",
            "status": True,
        },
    ]

    for account_data in accounts:
        client.post("/api/v1/account-information/", json=account_data)

    # Sort by username ascending
    response = client.get(
        "/api/v1/account-information/paged?sort=username&limit=10&page=1"
    )
    assert response.status_code == 200
    data = response.json()
    usernames = [item["username"] for item in data["items"]]
    assert usernames == sorted(usernames)

    # Sort by created_at descending
    response = client.get(
        "/api/v1/account-information/paged?sort=-created_at&limit=10&page=1"
    )
    assert response.status_code == 200
    data = response.json()
    created_ats = [
        item["created_at"] for item in data["items"] if item["created_at"]
    ]
    assert created_ats == sorted(created_ats, reverse=True)


def test_create_account_information_all_fields(client: TestClient):
    """Test creating account information with all fields."""
    account_data = {
        "first_name": "John",
        "last_name": "Doe",
        "middle_name": "Michael",
        "username": "jdoe_full",
        "password": "securepassword123",
        "designation": "Senior Pilot",
        "license_no": "LIC123456",
        "auth_stamp": "AUTH_STAMP_123",
        "status": True,
    }
    response = client.post("/api/v1/account-information/", json=account_data)
    assert response.status_code == 201
    data = response.json()
    assert data["first_name"] == account_data["first_name"]
    assert data["last_name"] == account_data["last_name"]
    assert data["middle_name"] == account_data["middle_name"]
    assert data["username"] == account_data["username"]
    assert data["designation"] == account_data["designation"]
    assert data["license_no"] == account_data["license_no"]
    assert data["auth_stamp"] == account_data["auth_stamp"]
    assert data["status"] == account_data["status"]


def test_create_account_information_minimal_fields(client: TestClient):
    """Test creating account information with only required fields."""
    account_data = {
        "first_name": "John",
        "last_name": "Doe",
        "username": "jdoe_minimal",
        "password": "securepassword123",
    }
    response = client.post("/api/v1/account-information/", json=account_data)
    assert response.status_code == 201
    data = response.json()
    assert data["first_name"] == account_data["first_name"]
    assert data["last_name"] == account_data["last_name"]
    assert data["username"] == account_data["username"]
    # Default status should be active (True)
    assert data["status"] == True


@pytest.mark.asyncio
async def test_list_account_informations_repository(
    db_session: AsyncSession
):
    """Test list_account_informations repository function."""
    items, total = await list_account_informations(
        session=db_session, limit=10, offset=0, search=None, sort=""
    )
    assert isinstance(total, int)
    assert total >= 0
    assert isinstance(items, list)


@pytest.mark.asyncio
async def test_create_account_information_repository(db_session: AsyncSession):
    """Test create_account_information repository function."""
    account_data = AccountInformationCreate(
        first_name="Test",
        last_name="User",
        username="testuser_repo",
        password="testpassword123",
        status=True,
    )
    created = await create_account_information(db_session, account_data)
    assert created.id is not None
    assert created.username == account_data.username
    assert created.first_name == account_data.first_name
    # Verify password is hashed (should not match plain password)
    account = await db_session.get(AccountInformation, created.id)
    assert account.password != account_data.password
    assert len(account.password) > 20  # Hashed password should be longer


@pytest.mark.asyncio
async def test_get_account_information_repository(db_session: AsyncSession):
    """Test get_account_information repository function."""
    # Create account first
    account_data = AccountInformationCreate(
        first_name="Test",
        last_name="User",
        username="testuser_get",
        password="testpassword123",
        status=True,
    )
    created = await create_account_information(db_session, account_data)

    # Get the account
    retrieved = await get_account_information(db_session, created.id)
    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.username == account_data.username

    # Test non-existent account
    not_found = await get_account_information(db_session, 999)
    assert not_found is None


@pytest.mark.asyncio
async def test_update_account_information_repository(db_session: AsyncSession):
    """Test update_account_information repository function."""
    # Create account first
    account_data = AccountInformationCreate(
        first_name="Test",
        last_name="User",
        username="testuser_update",
        password="testpassword123",
        status=True,
    )
    created = await create_account_information(db_session, account_data)

    # Update the account
    update_data = AccountInformationUpdate(
        first_name="Updated", designation="Pilot"
    )
    updated = await update_account_information(
        db_session, created.id, update_data
    )
    assert updated is not None
    assert updated.first_name == "Updated"
    assert updated.designation == "Pilot"
    # Other fields should remain unchanged
    assert updated.last_name == account_data.last_name

    # Test non-existent account
    not_found = await update_account_information(db_session, 999, update_data)
    assert not_found is None


@pytest.mark.asyncio
async def test_soft_delete_account_information_repository(
    db_session: AsyncSession
):
    """Test soft_delete_account_information repository function."""
    # Create account first
    account_data = AccountInformationCreate(
        first_name="Test",
        last_name="User",
        username="testuser_delete",
        password="testpassword123",
        status=True,
    )
    created = await create_account_information(db_session, account_data)

    # Soft delete the account
    deleted = await soft_delete_account_information(db_session, created.id)
    assert deleted is True

    # Verify it's soft deleted
    retrieved = await get_account_information(db_session, created.id)
    assert retrieved is None

    # Test deleting non-existent account
    not_found = await soft_delete_account_information(db_session, 999)
    assert not_found is False
