"""API router module."""

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/")
async def api_root() -> dict[str, str]:
    """API root endpoint."""
    return {"version": "v1", "message": "Doormat API"}
