"""Doormat - AI-first rental finder.

Main FastAPI application entry point.
"""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from doormat import metrics
from doormat.config import settings
from doormat.cost_tracking import get_cost_summary
from doormat.logging_config import get_logger, setup_logging

# Setup structured logging
setup_logging()
logger = get_logger("doormat.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> None:  # type: ignore[misc]
    """App lifecycle context manager."""
    logger.info("doormat_startup", version="0.1.0")
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


@app.middleware("http")
async def metrics_middleware(request: Request, call_next) -> PlainTextResponse:  # type: ignore[misc]
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

    return response  # type: ignore[return-value]


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


@app.get("/api/costs", tags=["monitoring"])
async def get_costs() -> dict[str, object]:
    """Get cost tracking summary."""
    return get_cost_summary()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "doormat.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_config=None,  # Use our structlog config
    )
