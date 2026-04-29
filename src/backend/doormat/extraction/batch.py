"""Policy-aware batch extraction for listing pages."""

import asyncio
import urllib.robotparser
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from doormat.extraction.orchestrator import extract_listing
from doormat.extraction.schemas import ListingExtractionResult
from doormat.models.orm import PropertyManager
from doormat.sources.urls import resolve_property_manager_scrape_url

logger = structlog.get_logger(__name__)


class ListingExtractor(Protocol):
    """Callable contract for extracting a single fetched listing page."""

    async def __call__(
        self,
        session: AsyncSession,
        html: str,
        url: str,
        property_manager: PropertyManager,
    ) -> ListingExtractionResult:
        """Extract a listing from fetched HTML."""


@dataclass(frozen=True)
class BatchExtractionPolicy:
    """Operational safety bounds for batch crawling."""

    user_agent: str = "DoormatBot/0.1"
    request_timeout_seconds: float = 10.0
    robots_timeout_seconds: float = 5.0
    max_urls: int = 50
    max_html_bytes: int = 1_000_000
    default_crawl_delay_seconds: float = 1.0
    max_crawl_delay_seconds: float = 30.0
    respect_robots: bool = True
    same_origin_only: bool = True
    allowed_content_types: tuple[str, ...] = ("text/html", "application/xhtml+xml")

    def __post_init__(self) -> None:
        """Reject nonsensical limits at construction time."""
        if self.max_urls < 1:
            raise ValueError("max_urls must be at least 1")
        if self.max_html_bytes < 1:
            raise ValueError("max_html_bytes must be at least 1")
        if self.request_timeout_seconds <= 0 or self.robots_timeout_seconds <= 0:
            raise ValueError("timeouts must be positive")


ClientFactory = Callable[[], AbstractAsyncContextManager[httpx.AsyncClient]]
Sleeper = Callable[[float], Awaitable[None]]


class BatchExtractor:
    """Fetch listing URLs safely, then delegate extraction to the AI pipeline."""

    def __init__(
        self,
        session: AsyncSession,
        property_manager: PropertyManager,
        *,
        policy: BatchExtractionPolicy | None = None,
        client_factory: ClientFactory | None = None,
        extractor: ListingExtractor = extract_listing,
        sleep: Sleeper = asyncio.sleep,
    ) -> None:
        self.session = session
        self.property_manager = property_manager
        self.policy = policy or BatchExtractionPolicy()
        self._client_factory = client_factory
        self._extractor = extractor
        self._sleep = sleep

        url = resolve_property_manager_scrape_url(property_manager) or ""
        parsed = urlparse(url)
        self.origin_netloc = parsed.netloc.lower()
        self.scheme = parsed.scheme or "https"

        self.rp = urllib.robotparser.RobotFileParser()
        self.robot_fetched = False
        self.robots_policy_loaded = False
        self.crawl_delay = self.policy.default_crawl_delay_seconds

    @asynccontextmanager
    async def _default_client(self) -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            yield client

    def _client_context(self) -> AbstractAsyncContextManager[httpx.AsyncClient]:
        if self._client_factory is not None:
            return self._client_factory()
        return self._default_client()

    async def _fetch_robots(self) -> None:
        """Fetch and parse robots.txt."""
        if self.robot_fetched or not self.policy.respect_robots or not self.origin_netloc:
            return

        robots_url = f"{self.scheme}://{self.origin_netloc}/robots.txt"
        async with self._client_context() as client:
            try:
                resp = await client.get(
                    robots_url,
                    timeout=self.policy.robots_timeout_seconds,
                    headers={"User-Agent": self.policy.user_agent},
                )
                if resp.status_code == 200:
                    self.rp.parse(resp.text.splitlines())
                    self.robots_policy_loaded = True
                    delay = self.rp.crawl_delay(self.policy.user_agent)
                    if delay:
                        self.crawl_delay = min(
                            max(float(delay), 0.0),
                            self.policy.max_crawl_delay_seconds,
                        )
            except Exception as e:
                logger.warning(
                    "robots_txt_fetch_failed",
                    domain=self.origin_netloc,
                    error_type=type(e).__name__,
                )

        self.robot_fetched = True

    async def process_urls(self, urls: list[str]) -> list[ListingExtractionResult]:
        """Process a list of listing URLs with rate limiting."""
        await self._fetch_robots()

        results: list[ListingExtractionResult] = []
        accepted_urls = list(self._iter_accepted_urls(urls))
        async with self._client_context() as client:
            for index, url in enumerate(accepted_urls):
                if (
                    self.policy.respect_robots
                    and self.robots_policy_loaded
                    and not self.rp.can_fetch(self.policy.user_agent, url)
                ):
                    logger.warning("robots_txt_disallowed", url=url)
                    continue

                try:
                    html = await self._fetch_html(client, url)
                    result = await self._extractor(
                        session=self.session,
                        html=html,
                        url=url,
                        property_manager=self.property_manager,
                    )
                    results.append(result)

                except Exception as e:
                    logger.error(
                        "batch_extraction_failed",
                        url=url,
                        error_type=type(e).__name__,
                    )

                if index < len(accepted_urls) - 1:
                    await self._sleep(self.crawl_delay)

        return results

    def _iter_accepted_urls(self, urls: Iterable[str]) -> Iterable[str]:
        """Yield unique, policy-compliant URLs up to the configured work bound."""
        seen: set[str] = set()
        for raw_url in urls:
            if len(seen) >= self.policy.max_urls:
                break
            normalized = self._normalize_listing_url(raw_url)
            if normalized is None or normalized in seen:
                continue
            seen.add(normalized)
            yield normalized

    def _normalize_listing_url(self, raw_url: str) -> str | None:
        """Reject non-web and cross-origin URLs before making network calls."""
        parsed = urlparse(raw_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            logger.warning("listing_url_rejected", url=raw_url, reason="unsupported_scheme")
            return None
        if parsed.username or parsed.password:
            logger.warning("listing_url_rejected", url=raw_url, reason="embedded_credentials")
            return None

        netloc = parsed.netloc.lower()
        if self.policy.same_origin_only and self.origin_netloc and netloc != self.origin_netloc:
            logger.warning("listing_url_rejected", url=raw_url, reason="cross_origin")
            return None

        return raw_url

    async def _fetch_html(self, client: httpx.AsyncClient, url: str) -> str:
        """Fetch one page and enforce response-type and size limits."""
        resp = await client.get(
            url,
            timeout=self.policy.request_timeout_seconds,
            headers={"User-Agent": self.policy.user_agent},
        )
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "").split(";")[0].strip().lower()
        if content_type and content_type not in self.policy.allowed_content_types:
            raise ValueError(f"unsupported content type: {content_type}")
        if len(resp.content) > self.policy.max_html_bytes:
            raise ValueError("response exceeds configured HTML size limit")
        return resp.text
