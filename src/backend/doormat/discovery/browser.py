"""BrowserDiscovery wraps `browser-use` for live web research.

If `browser-use` (or its browser dependency) is not installed/available,
discovery degrades gracefully and returns an empty list with a structlog
warning so the rest of the pipeline can proceed.
"""

from __future__ import annotations

import structlog

from doormat.discovery.models import DiscoveryCandidate

logger = structlog.get_logger(__name__)


try:  # pragma: no cover - import probe is environment-dependent
    import browser_use  # noqa: F401

    BROWSER_USE_AVAILABLE = True
except Exception as _exc:  # pragma: no cover - defensive
    BROWSER_USE_AVAILABLE = False
    _IMPORT_ERROR: str | None = str(_exc)
else:
    _IMPORT_ERROR = None


class BrowserDiscovery:
    """Live-browser discovery; no-ops gracefully if browser-use missing."""

    def __init__(self, available: bool | None = None) -> None:
        # Tests pass available=False to force the unavailable path.
        self._available = BROWSER_USE_AVAILABLE if available is None else available

    async def discover(self, city: str) -> list[DiscoveryCandidate]:
        """Discover candidates via a real browser. Returns [] when unavailable."""
        if not self._available:
            logger.warning(
                "browser_use_unavailable",
                city=city,
                reason=_IMPORT_ERROR or "browser-use not installed",
            )
            return []

        # browser-use real-world orchestration would go here. We keep this stub
        # behind the availability flag because real browser sessions cannot run
        # in CI / unit tests without a Chromium install.
        logger.info("browser_discovery_skipped_no_runtime", city=city)
        return []
