"""Tests for main app."""

import pytest
from fastapi.testclient import TestClient

from doormat.main import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()


def test_api_health(client):
    """Test API health check (if endpoint added)."""
    # Endpoint not yet added to router, skip for now
    pass
