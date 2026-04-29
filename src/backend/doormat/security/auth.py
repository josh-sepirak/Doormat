"""Shared optional bearer-token authentication for self-hosted APIs."""

from typing import Annotated

from fastapi import Header, HTTPException, status

from doormat.config import settings


async def require_bearer_auth(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Require AUTH_BEARER_TOKEN when it is configured.

    Doormat is single-user/self-hosted, so auth remains opt-in for local
    development. Once a token is configured, every sensitive API can share the
    same fail-closed dependency.
    """
    if not settings.AUTH_BEARER_TOKEN:
        return
    expected = f"Bearer {settings.AUTH_BEARER_TOKEN}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
