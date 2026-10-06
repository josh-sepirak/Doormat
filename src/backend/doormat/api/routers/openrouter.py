"""Proxy endpoint for fetching available OpenRouter models."""

from __future__ import annotations

from typing import Annotated

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from doormat.db.base import get_db
from doormat.models.orm import Preference
from doormat.security.auth import require_bearer_auth
from doormat.security.secrets import decrypt_secret

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/openrouter",
    tags=["openrouter"],
    dependencies=[Depends(require_bearer_auth)],
)
DbSession = Annotated[AsyncSession, Depends(get_db)]

# Hand-curated list of reliable paid models. Free models (`:free` suffix) are
# included automatically regardless of this list.
CURATED_PAID_MODELS = {
    # Anthropic
    "anthropic/claude-haiku-4-5",
    "anthropic/claude-3-haiku",
    "anthropic/claude-3-5-haiku",
    "anthropic/claude-sonnet-4-5",
    "anthropic/claude-3-5-sonnet",
    "anthropic/claude-3-7-sonnet",
    "anthropic/claude-opus-4",
    "anthropic/claude-3-opus",
    # OpenAI
    "openai/gpt-4o-mini",
    "openai/gpt-4o",
    "openai/gpt-4.1",
    "openai/gpt-4.1-mini",
    "openai/gpt-4.1-nano",
    "openai/o1-mini",
    "openai/o3-mini",
    "openai/o4-mini",
    # Google
    "google/gemini-flash-1.5",
    "google/gemini-flash-1.5-8b",
    "google/gemini-2.0-flash",
    "google/gemini-2.0-flash-lite",
    "google/gemini-pro-1.5",
    "google/gemini-2.5-pro",
    "google/gemini-2.5-flash",
    "google/gemini-2.5-flash-preview",
    "google/gemini-2.5-pro-preview",
    # Meta / Llama
    "meta-llama/llama-3.1-8b-instruct",
    "meta-llama/llama-3.1-70b-instruct",
    "meta-llama/llama-3.1-405b-instruct",
    "meta-llama/llama-3.2-3b-instruct",
    "meta-llama/llama-3.2-11b-vision-instruct",
    "meta-llama/llama-3.3-70b-instruct",
    "meta-llama/llama-4-scout",
    "meta-llama/llama-4-maverick",
    # Mistral
    "mistralai/mistral-7b-instruct",
    "mistralai/mistral-small",
    "mistralai/mistral-medium",
    "mistralai/mistral-large",
    "mistralai/mixtral-8x7b-instruct",
    "mistralai/mixtral-8x22b-instruct",
    "mistralai/codestral-mamba",
    # DeepSeek
    "deepseek/deepseek-chat",
    "deepseek/deepseek-chat-v3-0324",
    "deepseek/deepseek-r1",
    "deepseek/deepseek-r1-distill-llama-70b",
    "deepseek/deepseek-r1-distill-qwen-32b",
    "deepseek/deepseek-r1-0528",
    "deepseek/deepseek-prover-v2",
    # Qwen
    "qwen/qwen-2.5-7b-instruct",
    "qwen/qwen-2.5-72b-instruct",
    "qwen/qwen-2.5-coder-32b-instruct",
    "qwen/qwq-32b",
    "qwen/qwen3-0.6b",
    "qwen/qwen3-1.7b",
    "qwen/qwen3-4b",
    "qwen/qwen3-8b",
    "qwen/qwen3-14b",
    "qwen/qwen3-32b",
    "qwen/qwen3-30b-a3b",
    "qwen/qwen3-235b-a22b",
    # Cohere
    "cohere/command-r",
    "cohere/command-r-plus",
    "cohere/command-a",
    # Microsoft / Phi
    "microsoft/phi-4",
    "microsoft/phi-4-multimodal-instruct",
    # Amazon
    "amazon/nova-lite-v1",
    "amazon/nova-micro-v1",
    "amazon/nova-pro-v1",
    # xAI
    "x-ai/grok-3-mini-beta",
    "x-ai/grok-3-beta",
    # Moonshot
    "moonshotai/kimi-k2",
    "moonshotai/moonshot-v1-8k",
    "moonshotai/moonshot-v1-32k",
    # Nvidia
    "nvidia/llama-3.1-nemotron-70b-instruct",
}


def _extract_provider(model_id: str) -> str:
    """Extract and capitalize the provider prefix from a model ID.

    Handles `:free` suffix: 'meta-llama/llama-3.1-8b-instruct:free' → 'Meta-llama'
    """
    base = model_id.split(":")[0]  # strip :free or other suffixes
    prefix = base.split("/")[0] if "/" in base else base
    # Capitalize each hyphen-separated segment for readability
    return "-".join(p.capitalize() for p in prefix.split("-"))


def _display_name(model_id: str, raw_name: str) -> str:
    """Return a clean display name, appending ' (free)' for :free models."""
    if model_id.endswith(":free"):
        base_name = raw_name.replace(" (free)", "").replace(":free", "").strip()
        return f"{base_name} (free)"
    return raw_name


def _is_curated(model_id: str) -> bool:
    """Return True if the model should be shown in curated mode."""
    # Always include free models
    if model_id.endswith(":free"):
        return True
    # Strip any other suffixes (e.g. :nitro, :floor) for allowlist check
    base = model_id.split(":")[0]
    return base in CURATED_PAID_MODELS


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    context_length: int
    prompt_price: float  # USD per 1M tokens in
    completion_price: float


class ModelsRequest(BaseModel):
    """Request available OpenRouter models without putting secrets in URLs."""

    key: str | None = Field(None, min_length=10, max_length=255)
    preference_id: str | None = Field(None, max_length=36)
    curated: bool = True


async def _resolve_openrouter_key(body: ModelsRequest, session: AsyncSession) -> str:
    if body.key:
        return body.key.strip()
    if body.preference_id:
        preference = await session.get(Preference, body.preference_id)
        if preference and preference.openrouter_api_key:
            secret = decrypt_secret(preference.openrouter_api_key)
            if secret:
                return secret

    # Fallback to system-wide .env key
    from doormat.config import settings

    if settings.OPENROUTER_API_KEY:
        return settings.OPENROUTER_API_KEY

    raise HTTPException(status_code=400, detail="OpenRouter API key is required")


async def _fetch_openrouter_models(key: str) -> dict[str, object]:
    url = "https://openrouter.ai/api/v1/models"
    headers = {"Authorization": f"Bearer {key}"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, dict) else {"data": []}
    except httpx.HTTPStatusError as exc:
        logger.warning("openrouter_models_fetch_failed", status=exc.response.status_code)
        raise HTTPException(status_code=502, detail="OpenRouter API error") from exc
    except httpx.RequestError as exc:
        logger.warning("openrouter_models_network_error", error=str(exc))
        raise HTTPException(status_code=502, detail="Could not reach OpenRouter") from exc


def _model_info_from_payload(payload: dict[str, object], curated: bool) -> list[ModelInfo]:
    models: list[ModelInfo] = []
    raw_models = payload.get("data", [])
    if not isinstance(raw_models, list):
        return []
    for model in raw_models:
        item = _parse_model(model, curated)
        if item is not None:
            models.append(item)
    models.sort(key=lambda model: (model.prompt_price > 0, model.prompt_price, model.name))
    return models


def _parse_model(model: object, curated: bool) -> ModelInfo | None:
    if not isinstance(model, dict):
        return None
    model_id = str(model.get("id", ""))
    if not model_id or (curated and not _is_curated(model_id)):
        return None
    pricing = model.get("pricing", {})
    if not isinstance(pricing, dict):
        return None
    try:
        prompt_price = float(pricing.get("prompt", 0)) * 1_000_000
        completion_price = float(pricing.get("completion", 0)) * 1_000_000
    except (TypeError, ValueError):
        return None
    if prompt_price < 0 or completion_price < 0:
        return None
    raw_name = str(model.get("name", model_id))
    try:
        context_length = int(model.get("context_length", 0))
    except (TypeError, ValueError):
        context_length = 0
    return ModelInfo(
        id=model_id,
        name=_display_name(model_id, raw_name),
        provider=_extract_provider(model_id),
        context_length=context_length,
        prompt_price=prompt_price,
        completion_price=completion_price,
    )


@router.post("/models", response_model=list[ModelInfo])
async def list_models(
    body: ModelsRequest,
    session: DbSession,
) -> list[ModelInfo]:
    """Fetch OpenRouter models using the provided API key.

    When curated=true (default): returns the hand-picked paid model list plus
    ALL free models (`:free` suffix). When curated=false: returns everything.
    """
    key = await _resolve_openrouter_key(body, session)
    payload = await _fetch_openrouter_models(key)
    return _model_info_from_payload(payload, body.curated)
