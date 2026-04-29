"""Helpers for resolving usable scrape URLs for property managers."""

from __future__ import annotations

from doormat.models.orm import PropertyManager


def resolve_property_manager_scrape_url(property_manager: PropertyManager) -> str | None:
    """Return the best known URL to fetch for a property manager."""
    return property_manager.listing_page_url or property_manager.website
