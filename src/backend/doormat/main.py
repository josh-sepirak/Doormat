"""Doormat - AI-first rental finder.

Main FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from doormat.config import settings
from doormat.logging_config import get_logger, setup_logging

# Setup structured logging
setup_logging()
logger = get_logger("doormat.main")

# Create FastAPI app
app = FastAPI(
    title="Doormat",
    description="AI-first rental finder - autonomous property manager discovery and listing scoring",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    logger.info("health_check")
    return {"status": "ok", "service": "doormat"}


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "message": "Welcome to Doormat",
        "docs": "/api/docs",
        "version": "0.1.0",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "doormat.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_config=None,  # Use our structlog config
    )
