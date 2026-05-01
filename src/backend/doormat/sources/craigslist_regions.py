"""Load Craigslist regional reference points and rank by distance to a coordinate."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

from doormat import data as doormat_data_pkg

EARTH_MI = 3958.7613


@dataclass(frozen=True)
class CraigslistRegion:
    subdomain: str
    label: str
    lat: float
    lon: float
    country: str

    @property
    def url(self) -> str:
        return f"https://{self.subdomain}.craigslist.org"


@lru_cache(maxsize=1)
def load_regions() -> tuple[CraigslistRegion, ...]:
    raw = resources.files(doormat_data_pkg).joinpath("craigslist_regions.json").read_text(encoding="utf-8")
    rows = json.loads(raw)
    out: list[CraigslistRegion] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        try:
            out.append(
                CraigslistRegion(
                    subdomain=str(r["subdomain"]).lower(),
                    label=str(r["label"]),
                    lat=float(r["lat"]),
                    lon=float(r["lon"]),
                    country=str(r["country"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return tuple(out)


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return EARTH_MI * c


def nearest_regions(lat: float, lon: float, k: int = 3) -> list[tuple[CraigslistRegion, float]]:
    """Return up to ``k`` regions sorted by distance (miles) ascending."""
    scored: list[tuple[CraigslistRegion, float]] = []
    for region in load_regions():
        if region.lat == 0.0 and region.lon == 0.0:
            continue
        d = haversine_miles(lat, lon, region.lat, region.lon)
        scored.append((region, d))
    scored.sort(key=lambda x: x[1])
    return scored[: max(0, k)]


def region_by_subdomain(subdomain: str) -> CraigslistRegion | None:
    s = subdomain.strip().lower()
    for region in load_regions():
        if region.subdomain == s:
            return region
    return None
