"""Discover scrape targets from property manager websites."""

from __future__ import annotations

from typing import Final
from urllib.parse import ParseResult, urljoin, urlparse, urlunparse

import httpx
import structlog
from bs4 import BeautifulSoup

from doormat.models.orm import PropertyManager
from doormat.sources.urls import resolve_property_manager_scrape_url

logger = structlog.get_logger(__name__)

_USER_AGENT = "Doormat/1.0"

_PATH_KEYWORDS: Final[tuple[tuple[str, int], ...]] = (
    ("available", 4),
    ("availability", 4),
    ("floorplan", 4),
    ("floor-plans", 4),
    ("floorplans", 4),
    ("listing", 3),
    ("listings", 4),
    ("apartment", 3),
    ("apartments", 4),
    ("rent", 2),
    ("rental", 3),
    ("rentals", 4),
    ("property", 2),
    ("properties", 3),
    ("homes", 3),
    ("unit", 2),
    ("units", 3),
    ("vacancy", 3),
    ("vacancies", 3),
)
_TEXT_KEYWORDS: Final[tuple[tuple[str, int], ...]] = (
    ("available homes", 5),
    ("available units", 5),
    ("current availability", 5),
    ("view floor plans", 4),
    ("floor plans", 4),
    ("available", 3),
    ("availability", 3),
    ("listings", 4),
    ("listing", 3),
    ("apartments", 4),
    ("apartment", 3),
    ("rentals", 4),
    ("rental", 3),
    ("properties", 3),
    ("homes", 3),
    ("units", 3),
    ("vacancies", 3),
    ("vacancy", 3),
)


async def fetch_property_manager_scrape_pages(
    client: httpx.AsyncClient,
    property_manager: PropertyManager,
    *,
    max_candidate_links: int = 8,
) -> list[tuple[str, str]]:
    """Fetch the base page and any likely same-origin listing pages."""
    base_url = resolve_property_manager_scrape_url(property_manager)
    if not base_url:
        return []

    base_response = await client.get(base_url, headers={"User-Agent": _USER_AGENT})
    base_response.raise_for_status()

    pages: list[tuple[str, str]] = [(base_url, base_response.text)]
    candidate_urls = discover_candidate_listing_urls(
        base_response.text,
        base_url,
        limit=max_candidate_links,
    )
    seen_urls = {base_url}

    for candidate_url in candidate_urls:
        if candidate_url in seen_urls:
            continue
        try:
            response = await client.get(candidate_url, headers={"User-Agent": _USER_AGENT})
            response.raise_for_status()
        except Exception as exc:
            logger.warning(
                "scrape_candidate_fetch_failed",
                property_manager=property_manager.name,
                url=candidate_url,
                error_type=type(exc).__name__,
            )
            continue
        pages.append((candidate_url, response.text))
        seen_urls.add(candidate_url)

    return pages


def discover_candidate_listing_urls(
    html: str,
    base_url: str,
    *,
    limit: int = 8,
) -> list[str]:
    """Return same-origin links that look like listing pages."""
    soup = BeautifulSoup(html, "html.parser")
    base_host = _normalize_host(urlparse(base_url).netloc)
    candidates: dict[str, int] = {}

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href")
        if not isinstance(href, str):
            continue
        href = href.strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue

        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        if _normalize_host(parsed.netloc) != base_host:
            continue

        normalized = _normalize_url(parsed)
        score = _score_candidate(anchor.get_text(" ", strip=True), parsed.path, normalized)
        if score <= 0:
            continue
        current = candidates.get(normalized)
        if current is None or score > current:
            candidates[normalized] = score

    ordered = sorted(
        candidates.items(),
        key=lambda item: (-item[1], _path_depth(item[0]), item[0]),
    )
    return [url for url, _score in ordered[:limit]]


def _score_candidate(text: str, path: str, url: str) -> int:
    path_lower = path.lower()
    text_lower = text.lower()
    score = 0

    for keyword, weight in _PATH_KEYWORDS:
        if keyword in path_lower:
            score += weight
    for keyword, weight in _TEXT_KEYWORDS:
        if keyword in text_lower:
            score += weight

    if any(segment in path_lower for segment in ("/unit", "/floor", "/avail", "/listing", "/rent")):
        score += 1
    if "?" in url:
        score += 1
    return score


def _normalize_host(host: str) -> str:
    normalized = host.lower()
    if normalized.startswith("www."):
        normalized = normalized[4:]
    return normalized


def _normalize_url(parsed: ParseResult) -> str:
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse(parsed._replace(path=path, fragment=""))


def _path_depth(url: str) -> int:
    path = urlparse(url).path.strip("/")
    if not path:
        return 0
    return path.count("/") + 1
