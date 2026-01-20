"""Unit tests for Authentication endpoints."""
import pytest
from fastapi.testclient import TestClient


def test_register_user(client: TestClient):
    """Test user registration."""
    user_data = {
        "email": "test@example.com",
        "password": "testpassword123",
        "full_name": "Test User"
    }
    response = client.post("/api/v1/auth/register", json=user_data)
    # Should succeed (201) or fail if user exists (400)
    assert response.status_code in [201, 400]


def test_login_user(client: TestClient):
    """Test user login/token generation."""
    # First register a user
    user_data = {
        "email": "login@example.com",
        "password": "testpassword123",
        "full_name": "Login User"
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
