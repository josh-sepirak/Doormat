"""Tests for database session setup."""

import sqlite3
import tempfile
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command
from doormat.db.base import AsyncSessionLocal


@pytest.mark.asyncio
async def test_async_session_factory_creates_session():
    """The FastAPI DB dependency relies on this factory being callable."""
    session = AsyncSessionLocal()
    try:
        assert session is not None
    finally:
        await session.close()


def test_migration_includes_search_run_tables():
    """Alembic head must create durable search run tables and indexes (T006)."""
    with tempfile.TemporaryDirectory() as td:
        dbpath = Path(td) / "migrated.db"
        url = f"sqlite+aiosqlite:///{dbpath}"
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(cfg, "head")
        con = sqlite3.connect(dbpath)
        try:
            cur = con.execute("SELECT name FROM sqlite_master WHERE type='table'")
            names = {row[0] for row in cur.fetchall()}
            assert "search_runs" in names
            assert "search_run_events" in names
            assert "run_listing_results" in names
            idx = con.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
            index_names = {r[0] for r in idx}
            assert any("search_run" in n for n in index_names)
        finally:
            con.close()
