"""Discovery API router.

Endpoints:
  POST /api/discovery/cities/{city}            -> trigger discovery
  GET  /api/discovery/cities/{city}/managers   -> list discovered managers
  GET  /api/discovery/cities/{city}/status     -> discovery status
"""

from __future__ import annotations

import time
from collections import deque
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from doormat.config import settings
from doormat.db.base import get_db
from doormat.discovery.agent import DiscoveryAgent
from doormat.discovery.models import DiscoveryResult
from doormat.models.orm import PropertyManager

DBSession = Annotated[AsyncSession, Depends(get_db)]

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/discovery", tags=["discovery"])

_RATE_WINDOW_SECONDS = 60.0
_discovery_request_times: dict[str, deque[float]] = {}


class TriggerRequest(BaseModel):
    """Optional body for POST trigger."""

    preference_id: str | None = None


class ManagerOut(BaseModel):
    """Public representation of a discovered manager."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    city: str
    name: str
    website: str | None
    listing_page_url: str | None
    validated: bool


class CityStatus(BaseModel):
    """Discovery status for a city."""

    city: str
    managers_total: int
    managers_validated: int
    has_been_discovered: bool


async def require_discovery_auth(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Require bearer auth when AUTH_BEARER_TOKEN is configured."""
    if not settings.AUTH_BEARER_TOKEN:
        return

    expected = f"Bearer {settings.AUTH_BEARER_TOKEN}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def enforce_discovery_rate_limit(request: Request) -> None:
    """Apply a simple in-process per-client limit before LLM-backed discovery."""
    limit = settings.DISCOVERY_RATE_LIMIT_PER_MINUTE
    if limit <= 0:
        return

    now = time.monotonic()
    client_host = request.client.host if request.client else "unknown"
    request_times = _discovery_request_times.setdefault(client_host, deque())

    while request_times and now - request_times[0] >= _RATE_WINDOW_SECONDS:
        request_times.popleft()

    if len(request_times) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many discovery requests",
        )

    request_times.append(now)


def reset_discovery_rate_limits() -> None:
    """Clear rate-limit state for tests and local maintenance scripts."""
    _discovery_request_times.clear()


def _validate_city(city: str) -> str:
    """Validate city path parameter at the API boundary."""
    cleaned = city.strip()
    if not cleaned or len(cleaned) < 2 or len(cleaned) > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="city must be 2-100 chars",
        )
    return cleaned


@router.post("/cities/{city}", response_model=DiscoveryResult)
async def trigger_discovery(
    city: str,
    _auth: Annotated[None, Depends(require_discovery_auth)],
    _rate_limit: Annotated[None, Depends(enforce_discovery_rate_limit)],
    session: DBSession,
    body: TriggerRequest | None = None,
) -> DiscoveryResult:
    """Trigger a discovery run for the given city."""
    cleaned_city = _validate_city(city)
    pref_id = body.preference_id if body else None
    logger.info("api_trigger_discovery", city=cleaned_city, preference_id=pref_id)

    agent = DiscoveryAgent(session=session)
    try:
        return await agent.discover_city(cleaned_city, preference_id=pref_id)
    except Exception as exc:
        logger.error("api_discovery_failed", city=cleaned_city, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="discovery failed",
        ) from exc


@router.get("/cities/{city}/managers", response_model=list[ManagerOut])
async def list_managers(
    city: str,
    session: DBSession,
) -> list[ManagerOut]:
    """List discovered managers for a city."""
    cleaned_city = _validate_city(city)
    stmt = select(PropertyManager).where(PropertyManager.city == cleaned_city)
    rows = (await session.execute(stmt)).scalars().all()
    return [ManagerOut.model_validate(r) for r in rows]


@router.get("/cities/{city}/status", response_model=CityStatus)
async def city_status(
    city: str,
    session: DBSession,
) -> CityStatus:
    """Return discovery status for a city."""
    cleaned_city = _validate_city(city)
    stmt = select(PropertyManager).where(PropertyManager.city == cleaned_city)
    rows: list[Any] = list((await session.execute(stmt)).scalars().all())
    validated_count = sum(1 for r in rows if r.validated)
    return CityStatus(
        city=cleaned_city,
        managers_total=len(rows),
        managers_validated=validated_count,
        has_been_discovered=len(rows) > 0,
    )
