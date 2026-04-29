"""Configuration management for Doormat."""

from typing import Annotated, Any, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True
    )

    # App
    DEBUG: bool = False
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    API_VERSION: str = "v1"

    # CORS
    CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./doormat.db"
    DATABASE_ECHO: bool = False

    # Logging
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_FORMAT: Literal["json", "console"] = "console"

    # OpenRouter (LLM)
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Apify (anti-bot fallback)
    APIFY_API_TOKEN: str = ""

    # Cost tracking
    TRACK_COSTS: bool = True
    BUDGET_LIMIT_USD: float = 5.0

    # Optional bearer auth for exposed/self-hosted deployments
    AUTH_BEARER_TOKEN: str = ""

    # Local encryption key for BYOK secrets stored in SQLite.
    SECRET_KEY: str = ""

    # Expensive discovery endpoint protection
    DISCOVERY_RATE_LIMIT_PER_MINUTE: int = 10

    # Feature flag: Mode A0 (zero-cost API recipe extraction)
    # Set to False by default until Phase E (rollout + observability complete)
    API_RECIPE_ENABLED: bool = False

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        """Accept JSON/list values and simple comma-separated env strings."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, list) and all(isinstance(origin, str) for origin in value):
            return [str(origin) for origin in value]
        raise ValueError("CORS_ORIGINS must be a comma-separated string or list of strings")


# Global settings instance
settings = Settings()
