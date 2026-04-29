"""Apify actor wrappers for Zillow and Facebook Marketplace listing scraping."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Optional

import httpx
import structlog

logger = structlog.get_logger(__name__)

APIFY_BASE = "https://api.apify.com/v2"
ZILLOW_ACTOR = "maxime~zillow-scraper"
FACEBOOK_ACTOR = "apify~facebook-marketplace-scraper"

# Polling timeouts
_POLL_INTERVAL = 5.0
_MAX_WAIT = 180.0


@dataclass
class ApifyListing:
    url: str
    address: str
    price: Optional[float]
    bedrooms: Optional[int]
    bathrooms: Optional[float]
    sqft: Optional[int]
    description: Optional[str]
    photos: list[str]
    source: str


async def _run_actor(
    actor_id: str,
    input_data: dict[str, Any],
    api_token: str,
    timeout: float = _MAX_WAIT,
) -> list[dict[str, Any]]:
    """Run an Apify actor synchronously and return dataset items."""
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Start the run
        run_resp = await client.post(
            f"{APIFY_BASE}/acts/{actor_id}/runs",
            json=input_data,
            headers=headers,
        )
        run_resp.raise_for_status()
        run_data = run_resp.json()
        run_id = run_data.get("data", {}).get("id")
        if not run_id:
            logger.error("apify_run_no_id", actor=actor_id)
            return []

        # Poll until finished
        elapsed = 0.0
        while elapsed < timeout:
            await asyncio.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL
            status_resp = await client.get(
                f"{APIFY_BASE}/actor-runs/{run_id}",
                headers=headers,
            )
            status_resp.raise_for_status()
            status = status_resp.json().get("data", {}).get("status", "")
            if status in {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}:
                if status != "SUCCEEDED":
                    logger.warning("apify_run_non_success", actor=actor_id, status=status)
                    return []
                break
        else:
            logger.warning("apify_run_timed_out", actor=actor_id, elapsed=elapsed)
            return []

        # Fetch results
        dataset_id = run_data.get("data", {}).get("defaultDatasetId", "")
        items_resp = await client.get(
            f"{APIFY_BASE}/datasets/{dataset_id}/items",
            params={"format": "json", "limit": 100},
            headers=headers,
        )
        items_resp.raise_for_status()
        items = items_resp.json() or []
        if not items:
            logger.warning("apify_dataset_empty", actor=actor_id, dataset_id=dataset_id)
        return items


async def fetch_zillow_listings(
    city: str,
    api_token: str,
    max_results: int = 30,
) -> list[ApifyListing]:
    """Scrape rental listings from Zillow via Apify."""
    if not api_token:
        logger.info("zillow_skipped_no_token")
        return []

    logger.info("zillow_starting", city=city)
    try:
        items = await _run_actor(
            ZILLOW_ACTOR,
            {"search": f"{city}", "type": "rent", "maxItems": max_results},
            api_token,
        )
    except (httpx.HTTPError, TypeError, ValueError) as exc:
        logger.error("zillow_actor_failed", city=city, error=str(exc))
        return []

    listings: list[ApifyListing] = []
    for item in items:
        price = _coerce_float(item.get("price") or item.get("unformattedPrice"))
        address = _coerce_str(
            item.get("address") or item.get("streetAddress") or item.get("formattedAddress")
        )
        if not address:
            continue
        listings.append(
            ApifyListing(
                url=item.get("url") or item.get("detailUrl") or "",
                address=address,
                price=price,
                bedrooms=_coerce_int(item.get("bedrooms") or item.get("beds")),
                bathrooms=_coerce_float(item.get("bathrooms") or item.get("baths")),
                sqft=_coerce_int(item.get("livingArea") or item.get("sqft")),
                description=item.get("description"),
                photos=[p for p in (item.get("photos") or []) if isinstance(p, str)],
                source="zillow",
            )
        )

    logger.info("zillow_fetched", city=city, count=len(listings))
    return listings


async def fetch_facebook_listings(
    city: str,
    api_token: str,
    max_results: int = 30,
) -> list[ApifyListing]:
    """Scrape rental listings from Facebook Marketplace via Apify."""
    if not api_token:
        logger.info("facebook_skipped_no_token")
        return []

    logger.info("facebook_marketplace_starting", city=city)
    try:
        items = await _run_actor(
            FACEBOOK_ACTOR,
            {
                "startUrls": [
                    {
                        "url": (
                            f"https://www.facebook.com/marketplace/{city.lower().replace(' ', '_')}"
                            "/propertyrentals"
                        )
                    }
                ],
                "maxItems": max_results,
            },
            api_token,
        )
    except (httpx.HTTPError, TypeError, ValueError) as exc:
        logger.error("facebook_actor_failed", city=city, error=str(exc))
        return []

    listings: list[ApifyListing] = []
    for item in items:
        price = _coerce_float(item.get("price") or item.get("listing_price") or item.get("amount"))
        address = _coerce_str(
            item.get("address") or item.get("location_name") or item.get("location")
        )
        if not address:
            continue
        listings.append(
            ApifyListing(
                url=item.get("url") or item.get("productUrl") or "",
                address=address,
                price=price,
                bedrooms=_coerce_int(item.get("bedrooms") or item.get("num_bedrooms")),
                bathrooms=_coerce_float(item.get("bathrooms") or item.get("num_bathrooms")),
                sqft=_coerce_int(item.get("sqft") or item.get("living_area")),
                description=item.get("description") or item.get("story"),
                photos=[p for p in (item.get("photos") or []) if isinstance(p, str)],
                source="facebook",
            )
        )

    logger.info("facebook_fetched", city=city, count=len(listings))
    return listings


def _coerce_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(str(val).replace(",", "").replace("$", "").strip())
    except (ValueError, TypeError):
        return None


def _coerce_int(val: Any) -> Optional[int]:
    f = _coerce_float(val)
    return int(f) if f is not None else None


def _coerce_str(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()
