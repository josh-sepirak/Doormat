#!/usr/bin/env python3
"""Fetch CL sites HTML, geocode each region (Open-Meteo), emit JSON for the bundle.

Run from repo root:
  uv run python scripts/generate_craigslist_regions.py > src/backend/doormat/data/craigslist_regions.json

Requires network. Sleeps between requests (SLEEP_S) to respect the geocoding API.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

CL_SITES_URL = "https://www.craigslist.org/about/sites"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
USER_AGENT = "DoormatRegionGenerator/1.0 (https://github.com/)"
SLEEP_S = 0.11

# When Open-Meteo returns nothing, use these centroids (lat, lon, ISO country).
SUBDOMAIN_FALLBACK: dict[str, tuple[float, float, str]] = {
    "inlandempire": (34.1083, -117.2898, "US"),
    "sfbay": (37.7749, -122.4194, "US"),
    "goldcountry": (39.2366, -120.7721, "US"),
    "orangecounty": (33.7175, -117.8311, "US"),
    "ventura": (34.3705, -119.1391, "US"),
    "mohave": (35.2088, -114.0134, "US"),
    "imperial": (32.792, -115.563, "US"),
    "mendocino": (39.4457, -123.8053, "US"),
    "siskiyou": (41.7736, -122.4214, "US"),
    "yubasutter": (39.1409, -121.6167, "US"),
    "hanford": (36.3274, -119.6457, "US"),
    "visalia": (36.3302, -119.2921, "US"),
    "eastco": (39.2639, -103.6852, "US"),
    "westslope": (39.0639, -108.5506, "US"),
    "cnj": (40.2171, -74.7429, "US"),
    "southjersey": (39.8496, -74.4774, "US"),
    "jerseyshore": (39.9653, -74.0773, "US"),
    "nwct": (41.5582, -73.0515, "US"),
    "newlondon": (41.3557, -72.0995, "US"),
    "capecod": (41.6688, -70.2962, "US"),
    "westernmass": (42.1015, -72.5898, "US"),
    "southcoast": (41.6362, -70.9342, "US"),
    "worcester": (42.2626, -71.8023, "US"),
    "bham": (33.5207, -86.8025, "US"),
    "shoals": (34.7998, -87.6773, "US"),
    "gadsden": (33.7592, -86.5086, "US"),
    "akroncanton": (41.0814, -81.519, "US"),
    "ashtabula": (41.8651, -80.7898, "US"),
    "athensohio": (39.3292, -82.1013, "US"),
    "athensga": (33.9519, -83.3576, "US"),
    "thumb": (43.4194, -83.9508, "US"),
    "up": (46.5476, -87.3956, "US"),
    "bigbend": (30.2711, -103.6026, "US"),
    "collegestation": (30.628, -96.3344, "US"),
    "killeen": (31.1171, -97.7278, "US"),
    "easttexas": (32.3513, -95.3011, "US"),
    "deepeasttx": (31.3382, -94.7291, "US"),
    "sanmarcos": (29.8833, -97.9414, "US"),
    "texoma": (33.7537, -96.8357, "US"),
    "swva": (37.2709, -79.9414, "US"),
    "harrisonburg": (38.4496, -78.8689, "US"),
    "fredericksburg": (38.3032, -77.4605, "US"),
    "lynchburg": (37.4138, -79.1422, "US"),
    "blacksburg": (37.2297, -80.4139, "US"),
    "charlottesville": (38.0293, -78.4767, "US"),
    "easternshore": (37.5397, -75.8223, "US"),
    "md": (39.0458, -76.6413, "US"),
    "cnm": (35.0844, -106.6504, "US"),
    "scottsbluff": (41.8666, -103.6672, "US"),
    "micronesia": (7.4256, 151.7415, "FM"),
    "guam": (13.4443, 144.7937, "GU"),
}

# Map Craigslist h4 country / territory names to ISO 3166-1 alpha-2 for Open-Meteo.
COUNTRY_ISO: dict[str, str] = {
    "United Kingdom": "GB",
    "Russian Federation": "RU",
    "Czech Republic": "CZ",
    "United Arab Emirates": "AE",
    "Dominican Republic": "DO",
    "Costa Rica": "CR",
    "El Salvador": "SV",
    "Puerto Rico": "PR",
    "Virgin Islands, U.S.": "VI",
    "New Zealand": "NZ",
    "South Africa": "ZA",
    "United States": "US",
    "Germany": "DE",
    "France": "FR",
    "Italy": "IT",
    "Spain": "ES",
    "Netherlands": "NL",
    "Belgium": "BE",
    "Switzerland": "CH",
    "Austria": "AT",
    "Poland": "PL",
    "Romania": "RO",
    "Hungary": "HU",
    "Greece": "GR",
    "Portugal": "PT",
    "Sweden": "SE",
    "Norway": "NO",
    "Denmark": "DK",
    "Finland": "FI",
    "Ireland": "IE",
    "Ukraine": "UA",
    "Turkey": "TR",
    "Bulgaria": "BG",
    "Croatia": "HR",
    "Luxembourg": "LU",
    "Iceland": "IS",
    "China": "CN",
    "India": "IN",
    "Japan": "JP",
    "Korea": "KR",
    "Singapore": "SG",
    "Taiwan": "TW",
    "Thailand": "TH",
    "Vietnam": "VN",
    "Malaysia": "MY",
    "Indonesia": "ID",
    "Philippines": "PH",
    "Pakistan": "PK",
    "Bangladesh": "BD",
    "Israel and Palestine": "IL",
    "Iran": "IR",
    "Iraq": "IQ",
    "Kuwait": "KW",
    "Lebanon": "LB",
    "Hong Kong": "HK",
    "Australia": "AU",
    "Mexico": "MX",
    "Brazil": "BR",
    "Argentina": "AR",
    "Chile": "CL",
    "Colombia": "CO",
    "Peru": "PE",
    "Ecuador": "EC",
    "Guatemala": "GT",
    "Panama": "PA",
    "Uruguay": "UY",
    "Venezuela": "VE",
    "Bolivia": "BO",
    "Nicaragua": "NI",
    "Caribbean Islands": "JM",
    "Egypt": "EG",
    "Ethiopia": "ET",
    "Ghana": "GH",
    "Kenya": "KE",
    "Morocco": "MA",
    "Tunisia": "TN",
    "Nigeria": "NG",
    "South Korea": "KR",
    "Korea": "KR",
    "Guam / Micronesia": "GU",
    "Caribbean Islands": "JM",
    "Ethiopia": "ET",
    "Ghana": "GH",
    "Kenya": "KE",
    "Tunisia": "TN",
}


@dataclass
class Row:
    subdomain: str
    label: str
    country: str  # ISO2
    admin1: str | None  # US state / CA province


def _fetch_html() -> str:
    req = urllib.request.Request(CL_SITES_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _parse_rows(html: str) -> list[Row]:
    rows: list[Row] = []
    parts = re.split(r'<h2><a name="([A-Z]+)"></a>', html)
    for idx in range(1, len(parts), 2):
        section = parts[idx].strip()
        if idx + 1 >= len(parts):
            break
        chunk = parts[idx + 1]
        for h4_m, ul_html in re.findall(
            r"<h4>([^<]+)</h4>\s*<ul>(.*?)</ul>", chunk, flags=re.DOTALL
        ):
            region_title = re.sub(r"\s+", " ", h4_m.strip())
            admin1: str | None = None
            if section == "US":
                country = "US"
                admin1 = region_title
            elif section == "CA":
                country = "CA"
                admin1 = region_title
            else:
                admin1 = None
                country = COUNTRY_ISO.get(region_title, "US")
            for href, label in re.findall(
                r'<li><a href="https://([^.]+)\.craigslist\.org/?">([^<]+)</a></li>',
                ul_html,
            ):
                rows.append(
                    Row(
                        subdomain=href.strip().lower(),
                        label=re.sub(r"\s+", " ", label.strip()),
                        country=country,
                        admin1=admin1,
                    )
                )

    seen: set[str] = set()
    out: list[Row] = []
    for r in rows:
        if r.subdomain in seen:
            continue
        seen.add(r.subdomain)
        out.append(r)
    return out


def _geocode(name: str, country: str, admin1: str | None) -> tuple[float, float] | None:
    q = urllib.parse.urlencode({"name": name, "count": "1", "language": "en"})
    url = f"{GEOCODE_URL}?{q}"
    if len(country) == 2:
        url += f"&countryCode={urllib.parse.quote(country.upper())}"
    if admin1:
        url += f"&admin1={urllib.parse.quote(admin1)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    results = data.get("results") or []
    if not results:
        return None
    r0 = results[0]
    try:
        return float(r0["latitude"]), float(r0["longitude"])
    except (KeyError, TypeError, ValueError):
        return None


def _query_variants(row: Row) -> list[tuple[str, str | None]]:
    label = row.label
    first = re.split(r"\s*/\s*", label, maxsplit=1)[0].strip()
    out: list[tuple[str, str | None]] = [(label, row.admin1)]
    if first != label:
        out.append((first, row.admin1))
    return out


def _resolve_coords(row: Row) -> tuple[float, float, str]:
    if row.subdomain in SUBDOMAIN_FALLBACK:
        lat, lon, c = SUBDOMAIN_FALLBACK[row.subdomain]
        return lat, lon, c

    country = row.country.upper() if len(row.country) == 2 else "US"

    for qname, adm in _query_variants(row):
        time.sleep(SLEEP_S)
        coords = _geocode(qname, country=country, admin1=adm)
        if coords:
            lat, lon = coords
            return lat, lon, country

    time.sleep(SLEEP_S)
    coords = _geocode(row.subdomain.replace("_", " "), country, row.admin1)
    if coords:
        lat, lon = coords
        return lat, lon, country

    time.sleep(SLEEP_S)
    coords = _geocode(row.label.split("/")[0].strip(), country, None)
    if coords:
        lat, lon = coords
        return lat, lon, country

    return 20.0, 0.0, country


def main() -> None:
    html = _fetch_html()
    rows = _parse_rows(html)
    bundle: list[dict[str, str | float]] = []
    for i, row in enumerate(rows):
        lat, lon, country = _resolve_coords(row)
        bundle.append(
            {
                "subdomain": row.subdomain,
                "label": row.label,
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "country": country,
            }
        )
        if (i + 1) % 50 == 0:
            print(f"# progress {i + 1}/{len(rows)}", file=sys.stderr)
    json.dump(bundle, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
