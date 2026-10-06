"""Pytest configuration and fixtures."""

import asyncio
import os
import tempfile
from unittest.mock import AsyncMock

import pytest

# Point the app at a throwaway SQLite file BEFORE doormat.config is imported, so the
# test run never reads or writes a developer's real database.
_TEST_DB_DIR = tempfile.mkdtemp(prefix="doormat-tests-")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB_DIR}/test.db"

from doormat.config import settings  # noqa: E402
from doormat.db.base import Base, engine  # noqa: E402
from doormat.models import orm  # noqa: E402,F401  (registers every table on Base)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True, scope="session")
def test_secret_key():
    """Ensure SECRET_KEY is set for all tests that touch encryption."""
    original = settings.SECRET_KEY
    settings.SECRET_KEY = "test-secret-key-for-ci"
    yield
    settings.SECRET_KEY = original


@pytest.fixture(autouse=True, scope="session")
def create_test_tables():
    """Create every table in the throwaway database once per run."""

    async def _create() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(_create())


@pytest.fixture(autouse=True)
def no_startup_db_sweep(request, monkeypatch):
    """Keep app startup (lifespan) from running the orphaned-run sweep in every test.

    Tests that exercise the sweep itself opt out with @pytest.mark.real_startup_sweep.
    """
    if request.node.get_closest_marker("real_startup_sweep"):
        return
    monkeypatch.setattr("doormat.main._cleanup_orphaned_runs", AsyncMock())
