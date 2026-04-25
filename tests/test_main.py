"""Tests for main app."""

import pytest
from fastapi.testclient import TestClient

from doormat.main import app
from doormat.cost_tracking import get_cost_tracker, CostRecord, get_cost_summary


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_cost_tracker():
    """Clear cost tracker before each test."""
    get_cost_tracker().clear()
    yield
    get_cost_tracker().clear()


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


def test_metrics_endpoint(client):
    """Test Prometheus metrics endpoint."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"doormat_http_requests_total" in response.content
    assert b"doormat_llm_calls_total" in response.content


def test_costs_endpoint(client):
    """Test cost tracking summary endpoint."""
    response = client.get("/api/costs")
    assert response.status_code == 200
    data = response.json()
    assert "total_cost_usd" in data
    assert "total_tokens" in data
    assert "record_count" in data


def test_cost_tracking():
    """Test cost tracking functionality."""
    tracker = get_cost_tracker()

    record = CostRecord(
        service="openrouter",
        model="gpt-4",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cost_usd=0.01,
        latency_ms=1500.0,
    )
    tracker.add_record(record)

    assert tracker.total_cost() == pytest.approx(0.01)
    assert tracker.total_tokens() == 150
    assert len(tracker.records) == 1


def test_cost_summary():
    """Test cost summary generation."""
    tracker = get_cost_tracker()

    record1 = CostRecord(
        service="openrouter",
        model="gpt-4",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cost_usd=0.02,
    )
    record2 = CostRecord(
        service="apify",
        model=None,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        cost_usd=0.50,
    )

    tracker.add_record(record1)
    tracker.add_record(record2)

    summary = get_cost_summary()
    assert summary["total_cost_usd"] == pytest.approx(0.52)
    assert summary["total_tokens"] == 150
    assert summary["record_count"] == 2
    assert "by_service" in summary
    assert "openrouter" in summary["by_service"]
    assert "apify" in summary["by_service"]
