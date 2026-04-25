"""Tests for application configuration parsing."""

from doormat.config import Settings


def test_cors_origins_accept_comma_separated_env(monkeypatch):
    """Docker/.env friendly CORS_ORIGINS values should parse as a list."""
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")

    settings = Settings()

    assert settings.CORS_ORIGINS == ["http://localhost:3000", "http://localhost:5173"]


def test_default_host_is_localhost_bound(monkeypatch):
    """Local self-hosted default should not bind to every network interface."""
    monkeypatch.delenv("HOST", raising=False)

    settings = Settings()

    assert settings.HOST == "127.0.0.1"
