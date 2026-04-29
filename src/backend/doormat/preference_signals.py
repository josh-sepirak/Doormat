"""Heuristics for deriving structured signals from free-text preferences."""

from __future__ import annotations

import json
import re
from typing import Any

DEFAULT_SOURCES_ENABLED = ["craigslist"]

_MAX_PRICE_PATTERNS = (
    re.compile(
        r"(?:under|below|less than|max(?:imum)?|up to|at most|<=?)\s*\$?\s*"
        r"(?P<amount>\d[\d,]*(?:\.\d+)?)(?P<scale>k)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"\$?\s*(?P<amount>\d[\d,]*(?:\.\d+)?)(?P<scale>k)?\s*(?:max|budget)\b",
        re.IGNORECASE,
    ),
)
_BEDROOM_PATTERNS = (
    re.compile(r"\b(?P<count>\d+)\s*[- ]?(?:br|bed(?:room)?s?)\b", re.IGNORECASE),
    re.compile(r"\b(?P<count>\d+)\s*[- ]?(?:bedroom|bedrooms)\b", re.IGNORECASE),
)
_BATHROOM_PATTERNS = (
    re.compile(r"\b(?P<count>\d+(?:\.\d+)?)\s*[- ]?(?:ba|bath(?:room)?s?)\b", re.IGNORECASE),
    re.compile(r"\b(?P<count>\d+(?:\.\d+)?)\s*[- ]?(?:bathroom|bathrooms)\b", re.IGNORECASE),
)
_PET_POSITIVE_PATTERNS = (
    "pet friendly",
    "pet-friendly",
    "pets allowed",
    "pet allowed",
    "dogs allowed",
    "cats allowed",
    "pet ok",
    "pet okay",
    "pet-friendly",
)


def normalize_sources_enabled(raw: Any, default: list[str] | None = None) -> list[str]:
    """Normalize a stored JSON source list or sequence into a stable list."""
    fallback = list(default or DEFAULT_SOURCES_ENABLED)
    values: list[str]

    if raw is None:
        return fallback
    if isinstance(raw, list):
        values = [str(item).strip() for item in raw if isinstance(item, str) and item.strip()]
    elif isinstance(raw, str):
        if not raw.strip():
            return fallback
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return fallback
        if not isinstance(parsed, list):
            return fallback
        values = [str(item).strip() for item in parsed if isinstance(item, str) and item.strip()]
    else:
        return fallback

    deduped: list[str] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped or fallback


def extract_max_price(text: str) -> float | None:
    """Extract a max-rent signal from free-form preference text."""
    for pattern in _MAX_PRICE_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        value = _parse_numeric_amount(match.group("amount"), match.group("scale"))
        if value is not None:
            return value
    return None


def extract_min_bedrooms(text: str) -> int | None:
    """Extract a minimum bedroom count from free-form preference text."""
    for pattern in _BEDROOM_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        value = _parse_int_amount(match.group("count"))
        if value is not None:
            return value
    return None


def extract_min_bathrooms(text: str) -> float | None:
    """Extract a minimum bathroom count from free-form preference text."""
    for pattern in _BATHROOM_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        value = _parse_float_amount(match.group("count"))
        if value is not None:
            return value
    return None


def extract_pets_required(text: str) -> bool | None:
    """Detect whether the preference explicitly asks for pet-friendly housing."""
    lowered = text.lower()
    if any(phrase in lowered for phrase in _PET_POSITIVE_PATTERNS):
        return True
    return None


def derive_run_filter_overrides(
    description: str,
    sources_enabled_raw: Any = None,
) -> dict[str, Any]:
    """Derive structured filter overrides from the preference description."""
    filters: dict[str, Any] = {
        "sources_enabled": normalize_sources_enabled(sources_enabled_raw),
    }

    max_price = extract_max_price(description)
    if max_price is not None:
        filters["max_price"] = max_price

    min_bedrooms = extract_min_bedrooms(description)
    if min_bedrooms is not None:
        filters["min_bedrooms"] = min_bedrooms

    min_bathrooms = extract_min_bathrooms(description)
    if min_bathrooms is not None:
        filters["min_bathrooms"] = min_bathrooms

    pets_required = extract_pets_required(description)
    if pets_required is not None:
        filters["pets_required"] = pets_required

    return filters


def _parse_numeric_amount(amount: str, scale: str | None) -> float | None:
    try:
        value = float(amount.replace(",", ""))
    except ValueError:
        return None
    if scale:
        value *= 1000.0
    return value


def _parse_int_amount(value: str) -> int | None:
    try:
        return int(float(value))
    except ValueError:
        return None


def _parse_float_amount(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None
