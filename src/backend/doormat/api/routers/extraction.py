"""Extraction router."""

from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from doormat.api.routers.discovery import enforce_discovery_rate_limit, require_discovery_auth
from doormat.db.base import get_db
from doormat.extraction.orchestrator import extract_listing
from doormat.models.orm import Preference, PropertyManager

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/extraction", tags=["Extraction"])


class ExtractionRequest(BaseModel):
    property_manager_id: str = Field(..., min_length=1, max_length=36)
    preference_id: str | None = Field(None, min_length=1, max_length=36)
    url: HttpUrl
    html: str = Field(..., min_length=1, max_length=2_000_000)


class ExtractionResponse(BaseModel):
    status: Literal["success"]
    confidence: Literal["high", "medium", "low"]
    mode: Literal["A", "B"]
    listing_address: str


@router.post("/trigger", response_model=ExtractionResponse)
async def trigger_extraction(
    request: ExtractionRequest,
    _auth: Annotated[None, Depends(require_discovery_auth)],
    _rate_limit: Annotated[None, Depends(enforce_discovery_rate_limit)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExtractionResponse:
    """Trigger a manual extraction job."""

    # Fetch property manager
    stmt = select(PropertyManager).where(PropertyManager.id == request.property_manager_id)
    result = await db.execute(stmt)
    pm = result.scalars().first()

    if not pm:
        raise HTTPException(status_code=404, detail="Property manager not found")

    try:
        preference = None
        if request.preference_id:
            preference = await db.get(Preference, request.preference_id)
            if preference is None:
                raise HTTPException(status_code=404, detail="Preference not found")

        extraction_result = await extract_listing(
            session=db,
            html=request.html,
            url=str(request.url),
            property_manager=pm,
            preference=preference,
        )
        return ExtractionResponse(
            status="success",
            confidence=extraction_result.confidence,
            mode=extraction_result.mode,
            listing_address=extraction_result.listing.address,
        )
    except Exception as e:
        logger.error("extraction_job_failed", error=str(e))
        raise HTTPException(status_code=500, detail="extraction failed") from e
