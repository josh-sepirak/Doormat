"""CRUD for user-curated trusted listing sources."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal, Optional
from urllib.parse import urlparse

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from doormat.db.base import get_db
from doormat.models.orm import Listing, PropertyManager, TrustedSource
from doormat.security.auth import require_bearer_auth

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/trusted-sources",
    tags=["trusted-sources"],
    dependencies=[Depends(require_bearer_auth)],
)
DbSession = Annotated[AsyncSession, Depends(get_db)]

TrustedKind = Literal["craigslist_region", "property_manager"]
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class TrustedSourceOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    kind: str
    label: str
    url: str
    city: Optional[str] = None
    linked_property_manager_id: Optional[str] = None
    created_at: datetime


class TrustedSourceCreate(BaseModel):
    kind: TrustedKind
    label: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=8, max_length=2048)
    city: Optional[str] = Field(None, max_length=100)


class TrustedSourceTestResult(BaseModel):
    ok: bool
    status_code: Optional[int] = None
    detail: Optional[str] = None


def _canonical_craigslist_url(url: str) -> str:
    s = url.strip()
    if "://" not in s:
        s = "https://" + s
    p = urlparse(s)
    if p.scheme not in ("http", "https"):
        raise ValueError("URL must be http(s)")
    host = (p.netloc or "").lower()
    if not host.endswith(".craigslist.org"):
        raise ValueError("Craigslist region URL must be a *.craigslist.org host")
    sub = host.split(".")[0]
    if not sub:
        raise ValueError("Invalid Craigslist host")
    return f"https://{sub}.craigslist.org"


def _normalize_pm_url(url: str) -> str:
    s = url.strip()
    if not s.startswith(("http://", "https://")):
        s = "https://" + s
    p = urlparse(s)
    if p.scheme not in ("http", "https"):
        raise ValueError("URL must be http(s)")
    host = (p.netloc or "").lower()
    if not host or host in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("Invalid host")
    return s


async def _probe_url(url: str, timeout: float = 12.0) -> tuple[bool, Optional[int], Optional[str]]:
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    try:
        async with httpx.AsyncClient(
            headers=headers, follow_redirects=True, timeout=timeout
        ) as client:
            resp = await client.head(url)
            if resp.status_code >= 400:
                resp = await client.get(url)
            code = resp.status_code
            if 200 <= code < 400:
                return True, code, None
            return False, code, f"HTTP {code}"
    except httpx.HTTPError as exc:
        return False, None, str(exc)


@router.get("", response_model=list[TrustedSourceOut])
async def list_trusted_sources(
    session: DbSession,
    kind: Optional[str] = Query(None, max_length=32),
    city: Optional[str] = Query(None, max_length=100),
) -> list[TrustedSource]:
    stmt = select(TrustedSource).order_by(TrustedSource.created_at.desc())
    if kind:
        stmt = stmt.where(TrustedSource.kind == kind)
    if city:
        ck = city.strip().lower()
        stmt = stmt.where(
            or_(
                TrustedSource.city.is_(None),
                func.lower(TrustedSource.city) == ck,
                func.lower(TrustedSource.city).like(ck + ",%"),
                func.lower(TrustedSource.city).like(ck + " %"),
            )
        )
    rows = list((await session.execute(stmt)).scalars().all())
    return rows


@router.post("", response_model=TrustedSourceOut, status_code=status.HTTP_201_CREATED)
async def create_trusted_source(session: DbSession, body: TrustedSourceCreate) -> TrustedSource:
    if body.kind == "craigslist_region":
        try:
            canon = _canonical_craigslist_url(body.url)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        url = canon
    else:
        try:
            url = _normalize_pm_url(body.url)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    ok, code, err = await _probe_url(url)
    if not ok:
        raise HTTPException(
            status_code=422,
            detail=f"Could not reach URL ({err or 'unknown error'}, status={code})",
        )

    pm_id: Optional[str] = None
    if body.kind == "property_manager":
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        pm_city = (body.city or "").strip() or "Unknown"
        pm_id = str(uuid.uuid4())
        pm = PropertyManager(
            id=pm_id,
            city=pm_city[:100],
            name=body.label[:255],
            website=origin[:255],
            listing_page_url=url[:4096],
            validated=True,
            discovery_timestamp=datetime.now(UTC),
        )
        session.add(pm)

    ts = TrustedSource(
        id=str(uuid.uuid4()),
        kind=body.kind,
        label=body.label.strip()[:255],
        url=url,
        city=(body.city.strip()[:100] if body.city else None),
        linked_property_manager_id=pm_id,
        created_at=datetime.now(UTC),
    )
    session.add(ts)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        logger.warning("trusted_source_create_conflict", error=str(exc))
        raise HTTPException(
            status_code=409, detail="That URL is already saved for this kind"
        ) from exc

    await session.refresh(ts)
    return ts


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trusted_source(session: DbSession, source_id: str) -> None:
    row = await session.get(TrustedSource, source_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    pm_id = row.linked_property_manager_id
    await session.delete(row)
    await session.commit()

    if pm_id:
        n_listings = await session.scalar(
            select(func.count()).select_from(Listing).where(Listing.property_manager_id == pm_id)
        )
        if int(n_listings or 0) == 0:
            pm = await session.get(PropertyManager, pm_id)
            if pm:
                await session.delete(pm)
                await session.commit()


@router.post("/{source_id}/test", response_model=TrustedSourceTestResult)
async def test_trusted_source(session: DbSession, source_id: str) -> TrustedSourceTestResult:
    row = await session.get(TrustedSource, source_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    ok, code, err = await _probe_url(row.url)
    return TrustedSourceTestResult(ok=ok, status_code=code, detail=err)
