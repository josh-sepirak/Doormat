"""Pytest configuration and fixtures."""

import asyncio

import pytest

from doormat.config import settings


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
