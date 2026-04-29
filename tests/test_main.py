"""Tests for main app."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from doormat.cost_tracking import CostRecord, get_cost_summary, get_cost_tracker
from doormat.db.base import get_db
from doormat.main import app


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


def test_costs_endpoint():
    """Test cost tracking summary endpoint returns correct shape."""
    row = SimpleNamespace(total_cost=0.0, total_calls=0, total_tokens=0, cache_hits=0)
    mock_result = MagicMock()
    mock_result.one.return_value = row
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def _fake_db():
        yield mock_session

    app.dependency_overrides[get_db] = _fake_db
    try:
        with TestClient(app) as c:
            response = c.get("/api/costs/summary")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    data = response.json()
    assert "total_cost_usd" in data
    assert "total_calls" in data
    assert "budget_limit_usd" in data


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


@pytest.mark.asyncio
async def test_cleanup_orphaned_runs_marks_stuck_runs() -> None:
    """_cleanup_orphaned_runs must mark any 'running' SearchRun/DiscoveryRun as 'error'."""
    from doormat.main import _cleanup_orphaned_runs

    update_result = MagicMock()
    update_result.rowcount = 1

    session_mock = AsyncMock()
    session_mock.execute = AsyncMock(return_value=update_result)
    session_mock.commit = AsyncMock()
    # Make the session work as an async context manager.
    session_mock.__aenter__ = AsyncMock(return_value=session_mock)
    session_mock.__aexit__ = AsyncMock(return_value=False)

    with patch("doormat.main.AsyncSessionLocal", return_value=session_mock):
        await _cleanup_orphaned_runs()

    # One UPDATE for SearchRun, one for DiscoveryRun.
    assert session_mock.execute.await_count == 2
    session_mock.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_cleanup_orphaned_runs_noop_when_no_stuck_runs() -> None:
    """_cleanup_orphaned_runs should not log a warning when no runs are stuck."""
    from doormat.main import _cleanup_orphaned_runs

    update_result = MagicMock()
    update_result.rowcount = 0  # nothing updated

    session_mock = AsyncMock()
    session_mock.execute = AsyncMock(return_value=update_result)
    session_mock.commit = AsyncMock()
    session_mock.__aenter__ = AsyncMock(return_value=session_mock)
    session_mock.__aexit__ = AsyncMock(return_value=False)

    with patch("doormat.main.AsyncSessionLocal", return_value=session_mock):
        await _cleanup_orphaned_runs()  # should not raise

    session_mock.commit.assert_awaited_once()
