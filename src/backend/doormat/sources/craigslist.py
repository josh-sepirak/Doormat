"""Craigslist apartment listings scraper (direct httpx, no auth required)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import httpx
import structlog

logger = structlog.get_logger(__name__)

# Common Craigslist subdomain mappings for major metros
_CITY_TO_SUBDOMAIN: dict[str, str] = {
    "san francisco": "sfbay",
    "sf": "sfbay",
    "los angeles": "losangeles",
    "la": "losangeles",
    "new york": "newyork",
    "nyc": "newyork",
    "new york city": "newyork",
    "chicago": "chicago",
    "seattle": "seattle",
    "portland": "portland",
    "austin": "austin",
    "denver": "denver",
    "boston": "boston",
    "atlanta": "atlanta",
    "miami": "miami",
    "dallas": "dallas",
    "houston": "houston",
    "phoenix": "phoenix",
    "san diego": "sandiego",
    "minneapolis": "minneapolis",
    "detroit": "detroit",
    "philadelphia": "philadelphia",
    "washington": "washingtondc",
    "dc": "washingtondc",
    "nashville": "nashville",
    "charlotte": "charlotte",
    "raleigh": "raleigh",
    "salt lake city": "saltlake",
    "las vegas": "lasvegas",
    "sacramento": "sacramento",
    "san jose": "sfbay",
    "oakland": "sfbay",
    "brooklyn": "newyork",
    "manhattan": "newyork",
    "queens": "newyork",
    "bronx": "newyork",
}


@dataclass
class CraigslistListing:
    url: str
    title: str
    price: Optional[float]
    bedrooms: Optional[int]
    neighborhood: Optional[str]
    address: Optional[str]


def _city_to_subdomain(city: str) -> str:
    # Strip state suffix like ", TX" or ", CA" before normalizing
    normalized = re.sub(r",\s*[a-z]{2}$", "", city.strip().lower()).strip()
    if normalized in _CITY_TO_SUBDOMAIN:
        return _CITY_TO_SUBDOMAIN[normalized]
    # Fall back: strip spaces/special chars
    return re.sub(r"[^a-z0-9]", "", normalized)


def _parse_price(text: str) -> Optional[float]:
    m = re.search(r"\$(\d[\d,]*)", text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def _parse_bedrooms(text: str) -> Optional[int]:
    m = re.search(r"(\d+)\s*br", text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return None


async def fetch_craigslist_listings(
    city: str,
    max_results: int = 30,
    timeout: float = 20.0,
    subdomain: Optional[str] = None,
) -> list[CraigslistListing]:
    """Scrape apartment listings from Craigslist for a given city.

    When ``subdomain`` is set (e.g. ``inlandempire``), that regional site is used
    instead of inferring from ``city``.
    """
    sub = (subdomain or "").strip().lower().replace(".craigslist.org", "")
    if not sub:
        sub = _city_to_subdomain(city)
    base_url = f"https://{sub}.craigslist.org"
    search_url = f"{base_url}/search/apa?availabilityMode=0&sale_date=all+dates"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        async with httpx.AsyncClient(
            headers=headers,
            follow_redirects=True,
            timeout=timeout,
        ) as client:
            resp = await client.get(search_url)
            resp.raise_for_status()
            html = resp.text
    except httpx.HTTPError as exc:
        logger.warning("craigslist_fetch_failed", city=city, subdomain=sub, error=str(exc))
        return []

    listings = _parse_search_results(html, base_url, max_results)
    if not listings:
        logger.warning("craigslist_parse_returned_no_listings", city=city, subdomain=sub)
    logger.info("craigslist_fetched", city=city, subdomain=sub, count=len(listings))
    return listings


def _parse_search_results(html: str, base_url: str, max_results: int) -> list[CraigslistListing]:
    """Parse Craigslist search results HTML without BeautifulSoup dependency.

    Craigslist now renders listings inside <ol class="cl-static-search-results"> for
    crawler/no-JS clients. Each <li> contains an <a href="full-url"> with child divs
    for title, price, and location.
    """
    listings: list[CraigslistListing] = []

    # Extract the static results container
    ol_m = re.search(r'<ol[^>]*class="cl-static-search-results"[^>]*>(.*?)</ol>', html, re.DOTALL)
    if not ol_m:
        return listings

    ol_html = ol_m.group(1)

    # Each <li> block
    item_pattern = re.compile(r"<li[^>]*>(.*?)</li>", re.DOTALL)
    href_pattern = re.compile(r'href="(https?://[^"]+/d/[^"]+/\d+\.html)"')
    title_pattern = re.compile(r'<div[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</div>', re.DOTALL)
    price_pattern = re.compile(r'<div[^>]*class="[^"]*price[^"]*"[^>]*>([^<]+)</div>')
    location_pattern = re.compile(
        r'<div[^>]*class="[^"]*location[^"]*"[^>]*>(.*?)</div>', re.DOTALL
    )

    for m in item_pattern.finditer(ol_html):
        if len(listings) >= max_results:
            break
        block = m.group(1)

        href_m = href_pattern.search(block)
        if not href_m:
            continue
        url = href_m.group(1)

        title = ""
        title_m = title_pattern.search(block)
        if title_m:
            # Strip any nested tags (e.g. <span>) and HTML entities
            raw = re.sub(r"<[^>]+>", "", title_m.group(1))
            title = re.sub(r"&#\d+;", lambda x: chr(int(x.group()[2:-1])), raw).strip()
            title = (
                title.replace("&amp;", "&")
                .replace("&lt;", "<")
                .replace("&gt;", ">")
                .replace("&quot;", '"')
                .replace("&#39;", "'")
            )

        price: Optional[float] = None
        price_m = price_pattern.search(block)
        if price_m:
            price = _parse_price(price_m.group(1))

        address: Optional[str] = None
        loc_m = location_pattern.search(block)
        if loc_m:
            raw_loc = re.sub(r"<[^>]+>", "", loc_m.group(1)).strip()
            if raw_loc:
                address = raw_loc

        # Bedroom count sometimes embedded in URL slug (e.g. /2br-apt/)
        bedrooms = _parse_bedrooms(url)

        listings.append(
            CraigslistListing(
                url=url,
                title=title,
                price=price,
                bedrooms=bedrooms,
                neighborhood=address,
                address=address,
            )
        )

    return listings
