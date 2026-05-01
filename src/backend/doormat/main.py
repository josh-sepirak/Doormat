"""Doormat - AI-first rental finder.

Main FastAPI application entry point.
"""

import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import update

from doormat import metrics
from doormat.api.routers.config import router as config_router
from doormat.api.routers.costs import router as costs_router
from doormat.api.routers.craigslist_regions import router as craigslist_regions_router
from doormat.api.routers.discovery import router as discovery_router
from doormat.api.routers.extraction import router as extraction_router
from doormat.api.routers.listings import router as listings_router
from doormat.api.routers.openrouter import router as openrouter_router
from doormat.api.routers.preferences import router as preferences_router
from doormat.api.routers.search_runs import router as search_runs_router
from doormat.api.routers.trusted_sources import router as trusted_sources_router
from doormat.config import settings
from doormat.cost_tracking import get_cost_summary
from doormat.db.base import AsyncSessionLocal
from doormat.logging_config import get_logger, setup_logging
from doormat.models.orm import DiscoveryRun, SearchRun

# Setup structured logging
setup_logging()
logger = get_logger("doormat.main")


async def _cleanup_orphaned_runs() -> None:
    """Mark any runs left in 'running' state (from a prior server crash) as 'error'."""
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as session:
        sr_result = await session.execute(
            update(SearchRun)
            .where(SearchRun.status == "running")
            .values(status="error", finished_at=now)
        )
        dr_result = await session.execute(
            update(DiscoveryRun)
            .where(DiscoveryRun.status == "running")
            .values(status="error", finished_at=now)
        )
        await session.commit()
        sr_count = sr_result.rowcount
        dr_count = dr_result.rowcount
        if sr_count or dr_count:
            logger.warning(
                "orphaned_runs_cleaned_on_startup",
                search_runs=sr_count,
                discovery_runs=dr_count,
            )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """App lifecycle context manager."""
    logger.info("doormat_startup", version="0.1.0")
    await _cleanup_orphaned_runs()
    yield
    logger.info("doormat_shutdown")


# Create FastAPI app
app = FastAPI(
    title="Doormat",
    description="AI-first rental finder - autonomous property manager discovery and listing scoring",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(config_router)
app.include_router(costs_router)
app.include_router(craigslist_regions_router)
app.include_router(discovery_router)
app.include_router(extraction_router)
app.include_router(listings_router)
app.include_router(preferences_router)
app.include_router(search_runs_router)
app.include_router(trusted_sources_router)
app.include_router(openrouter_router)


@app.middleware("http")
async def metrics_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Middleware to track HTTP request metrics."""
    path = request.url.path
    method = request.method

    metrics.increment_active_requests()
    start_time = time.time()

    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as e:
        status_code = 500
        logger.error("request_error", path=path, method=method, error=str(e))
        raise
    finally:
        duration_ms = (time.time() - start_time) * 1000
        metrics.record_http_request(method, path, status_code, duration_ms)
        metrics.decrement_active_requests()
        logger.info(
            "http_request",
            method=method,
            path=path,
            status=status_code,
            duration_ms=duration_ms,
        )

    return response


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


@app.get("/metrics", tags=["monitoring"])
async def get_metrics() -> PlainTextResponse:
    """Prometheus metrics endpoint."""
    # Update cost gauge from tracker
    cost_summary = get_cost_summary()
    cost_usd = cost_summary.get("total_cost_usd", 0.0)
    if isinstance(cost_usd, (int, float)):
        metrics.update_cost_gauge(float(cost_usd))

    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "doormat.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_config=None,  # Use our structlog config
    )
