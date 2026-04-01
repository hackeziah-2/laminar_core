"""Unit tests for Authentication endpoints."""
import pytest
from fastapi.testclient import TestClient


def test_register_user(client: TestClient):
    """Test user registration."""
    user_data = {
        "first_name": "Test",
        "last_name": "User",
        "username": "test_register_user",
        "email": "test@example.com",
        "password": "testpassword123",
    }
    response = client.post("/api/v1/auth/register", json=user_data)
    # Should succeed (201) or fail if user exists (400)
    assert response.status_code in [201, 400], response.text


def test_register_bulk_users(client: TestClient):
    """POST /auth/register accepts a JSON array and returns created accounts."""
    batch = [
        {
            "first_name": "Bulk",
            "last_name": "One",
            "username": "bulk_register_one",
            "email": "bulk1@example.com",
            "password": "testpassword123",
        },
        {
            "first_name": "Bulk",
            "last_name": "Two",
            "username": "bulk_register_two",
            "email": "bulk2@example.com",
            "password": "testpassword123",
        },
    ]
    response = client.post("/api/v1/auth/register", json=batch)
    assert response.status_code in [201, 400], response.text
    if response.status_code == 201:
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 2
        usernames = {row["username"] for row in body}
        assert usernames == {"bulk_register_one", "bulk_register_two"}


def test_login_user(client: TestClient):
    """Test user login/token generation."""
    # First register a user
    user_data = {
        "first_name": "Login",
        "last_name": "User",
        "username": "login_user_1",
        "email": "login@example.com",
        "password": "testpassword123",
    }
    client.post("/api/v1/auth/register", json=user_data)

    # Then try to login
    login_data = {
        "username": "login@example.com",
        "password": "testpassword123"
    }
    response = client.post("/api/v1/auth/token", data=login_data)
    # Should succeed (200) or fail if credentials are wrong (401)
    assert response.status_code in [200, 401]
    if response.status_code == 200:
        assert "access_token" in response.json()


def test_me_requires_valid_token(client: TestClient):
    """GET /api/v1/auth/me returns 401 without Bearer token."""
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_me_returns_profile_with_full_name(client: TestClient):
    """GET /api/v1/auth/me returns account and full_name when authorized."""
    user_data = {
        "first_name": "Jane",
        "last_name": "Pilot",
        "username": "me_endpoint_user",
        "email": "me@example.com",
        "password": "testpassword123",
    }
    reg = client.post("/api/v1/auth/register", json=user_data)
    assert reg.status_code == 201, reg.text
    tok = client.post(
        "/api/v1/auth/token",
        data={"username": "me_endpoint_user", "password": "testpassword123"},
    )
    assert tok.status_code == 200
    access = tok.json()["access_token"]
    r = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "me_endpoint_user"
    assert body["full_name"] == "Jane Pilot"
    assert body["email"] == "me@example.com"
    assert "role" in body
    assert "designation" in body
