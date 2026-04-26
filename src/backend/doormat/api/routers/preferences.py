"""Preference API endpoints."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from doormat.db.base import get_db
from doormat.models.orm import Preference
from doormat.schemas import PreferenceCreate, PreferenceResponse, PreferenceUpdate

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/preferences", tags=["preferences"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=list[PreferenceResponse])
async def list_preferences(session: DbSession) -> list[Preference]:
    """Return saved search preferences, newest first."""
    result = await session.execute(select(Preference).order_by(Preference.created_at.desc()))
    return list(result.scalars().all())


@router.post("", response_model=PreferenceResponse, status_code=status.HTTP_201_CREATED)
async def create_preference(body: PreferenceCreate, session: DbSession) -> Preference:
    """Create a natural-language search preference."""
    now = datetime.now(UTC)
    preference = Preference(
        id=str(uuid.uuid4()),
        description=body.description.strip(),
        city=body.city.strip(),
        created_at=now,
        updated_at=now,
    )
    session.add(preference)
    await session.commit()

    logger.info("preference_created", preference_id=preference.id, city=preference.city)
    return preference


@router.patch("/{preference_id}", response_model=PreferenceResponse)
async def update_preference(
    preference_id: str,
    body: PreferenceUpdate,
    session: DbSession,
) -> Preference:
    """Update an existing search preference."""
    result = await session.execute(select(Preference).where(Preference.id == preference_id))
    preference = result.scalar_one_or_none()
    if preference is None:
        raise HTTPException(status_code=404, detail="Preference not found")

    if body.description is not None:
        preference.description = body.description.strip()
    if body.city is not None:
        preference.city = body.city.strip()
    preference.updated_at = datetime.now(UTC)

    await session.commit()
    logger.info("preference_updated", preference_id=preference.id)
    return preference


@router.delete("/{preference_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_preference(preference_id: str, session: DbSession) -> Response:
    """Delete a saved search preference."""
    result = await session.execute(select(Preference).where(Preference.id == preference_id))
    preference = result.scalar_one_or_none()
    if preference is None:
        raise HTTPException(status_code=404, detail="Preference not found")

    await session.delete(preference)
    await session.commit()
    logger.info("preference_deleted", preference_id=preference_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
