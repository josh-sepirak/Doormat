from fastapi import APIRouter, Depends
from pydantic import BaseModel

from doormat.config import settings
from doormat.security.auth import require_bearer_auth

router = APIRouter(
    prefix="/api/config",
    tags=["config"],
    dependencies=[Depends(require_bearer_auth)],
)


class SystemConfig(BaseModel):
    has_openrouter_key: bool
    openrouter_key_last4: str | None
    has_apify_token: bool
    apify_token_last4: str | None


@router.get("", response_model=SystemConfig)
async def get_system_config():
    """Return whether system-wide keys are configured in .env."""

    def last4(s: str | None) -> str | None:
        if not s or len(s) < 8:
            return None
        return s[-4:]

    return SystemConfig(
        has_openrouter_key=bool(settings.OPENROUTER_API_KEY),
        openrouter_key_last4=last4(settings.OPENROUTER_API_KEY),
        has_apify_token=bool(settings.APIFY_API_TOKEN),
        apify_token_last4=last4(settings.APIFY_API_TOKEN),
    )
