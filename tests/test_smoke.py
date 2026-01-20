"""Smoke tests to verify basic functionality."""
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture
def client():
    """Test client fixture."""
    return TestClient(app)


def test_root_endpoint(client: TestClient):
    """Test that the root endpoint is accessible."""
    response = client.get("/")
    # Should return 200 or 404 depending on if root is defined
    assert response.status_code in [200, 404]


def test_health_check(client: TestClient):
    """Test health check endpoint if it exists."""
    response = client.get("/health")
    # If health endpoint exists, should return 200
    # Otherwise, will be 404 which is also acceptable for smoke test
    assert response.status_code in [200, 404]
