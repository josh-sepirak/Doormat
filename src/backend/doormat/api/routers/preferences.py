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
from doormat.security.auth import require_bearer_auth
from doormat.security.secrets import encrypt_secret, is_encrypted_secret

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/preferences",
    tags=["preferences"],
    dependencies=[Depends(require_bearer_auth)],
)
DbSession = Annotated[AsyncSession, Depends(get_db)]


def _clean_optional_string(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _encrypt_optional_secret(value: str | None) -> str | None:
    try:
        return encrypt_secret(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="SECRET_KEY must be configured before saving API keys",
        ) from exc


def _maybe_encrypt_legacy_secret(value: str | None) -> tuple[str | None, bool]:
    if not value or is_encrypted_secret(value):
        return value, False
    try:
        encrypted = encrypt_secret(value)
    except ValueError:
        return value, False
    return encrypted, encrypted != value


@router.get("", response_model=list[PreferenceResponse])
async def list_preferences(session: DbSession) -> list[Preference]:
    """Return saved search preferences, newest first."""
    result = await session.execute(select(Preference).order_by(Preference.created_at.desc()))
    preferences = list(result.scalars().all())
    changed = False
    for preference in preferences:
        preference.openrouter_api_key, openrouter_changed = _maybe_encrypt_legacy_secret(
            preference.openrouter_api_key
        )
        preference.apify_api_token, apify_changed = _maybe_encrypt_legacy_secret(
            preference.apify_api_token
        )
        changed = changed or openrouter_changed or apify_changed
    if changed:
        await session.commit()
    return preferences


@router.post("", response_model=PreferenceResponse, status_code=status.HTTP_201_CREATED)
async def create_preference(body: PreferenceCreate, session: DbSession) -> Preference:
    """Create a natural-language search preference."""
    now = datetime.now(UTC)
    preference = Preference(
        id=str(uuid.uuid4()),
        description=body.description.strip(),
        city=body.city.strip(),
        api_provider=body.api_provider,
        openrouter_api_key=_encrypt_optional_secret(body.openrouter_api_key),
        apify_api_token=_encrypt_optional_secret(body.apify_api_token),
        fast_model=_clean_optional_string(body.fast_model),
        smart_model=_clean_optional_string(body.smart_model),
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
    if body.api_provider is not None:
        preference.api_provider = body.api_provider
    fields_set = body.model_fields_set
    if "openrouter_api_key" in fields_set:
        preference.openrouter_api_key = _encrypt_optional_secret(body.openrouter_api_key)
    if "apify_api_token" in fields_set:
        preference.apify_api_token = _encrypt_optional_secret(body.apify_api_token)
    if body.fast_model is not None:
        preference.fast_model = _clean_optional_string(body.fast_model)
    if body.smart_model is not None:
        preference.smart_model = _clean_optional_string(body.smart_model)
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
