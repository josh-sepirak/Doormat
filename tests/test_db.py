"""Tests for database session setup."""

import pytest

from doormat.db.base import AsyncSessionLocal


@pytest.mark.asyncio
async def test_async_session_factory_creates_session():
    """The FastAPI DB dependency relies on this factory being callable."""
    session = AsyncSessionLocal()
    try:
        assert session is not None
    finally:
        await session.close()
