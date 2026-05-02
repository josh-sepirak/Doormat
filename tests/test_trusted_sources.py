"""Tests for Craigslist regions and trusted sources."""

import pytest

from doormat.sources.craigslist_regions import (
    load_regions,
    nearest_regions,
    region_by_subdomain,
    haversine_miles,
)


class TestCraigslistRegions:
    """Tests for craigslist_regions module."""
    
    def test_load_regions(self):
        """Load regions from bundled JSON."""
        regions = load_regions()
        assert len(regions) > 0
        assert all(hasattr(r, "subdomain") for r in regions)
        assert all(hasattr(r, "label") for r in regions)
    
    def test_load_regions_cached(self):
        """Regions are cached after first load."""
        r1 = load_regions()
        r2 = load_regions()
        assert r1 is r2  # Same object (cached)
    
    def test_haversine_distance(self):
        """Haversine distance calculation."""
        # SF to LA is roughly 380 miles
        sf_lat, sf_lon = 37.7749, -122.4194
        la_lat, la_lon = 34.0522, -118.2437
        distance = haversine_miles(sf_lat, sf_lon, la_lat, la_lon)
        assert 340 < distance < 390  # Approximately 347-360 miles
    
    def test_nearest_regions(self):
        """Find nearest regions by distance."""
        # Lancaster, CA coordinates
        lancaster_lat, lancaster_lon = 34.6867, -118.2594
        nearest = nearest_regions(lancaster_lat, lancaster_lon, k=3)
        
        assert len(nearest) > 0
        # First result should be closest
        assert nearest[0][1] <= nearest[-1][1]  # Distances are sorted ascending
    
    def test_inland_empire_near_lancaster_ca(self):
        """Inland Empire should be one of top suggestions for Lancaster, CA (SC-001)."""
        lancaster_lat, lancaster_lon = 34.6867, -118.2594
        nearest = nearest_regions(lancaster_lat, lancaster_lon, k=5)
        
        subdomains = [r.subdomain for r, _ in nearest]
        # Inland Empire should be in top 5 closest regions
        assert "inlandempire" in subdomains, f"Expected Inland Empire in {subdomains}"
    
    def test_region_by_subdomain(self):
        """Lookup region by subdomain."""
        region = region_by_subdomain("sfbay")
        assert region is not None
        assert region.subdomain == "sfbay"
        assert "bay" in region.label.lower() or "francisco" in region.label.lower()
    
    def test_region_by_subdomain_case_insensitive(self):
        """Subdomain lookup is case-insensitive."""
        region1 = region_by_subdomain("SFBAY")
        region2 = region_by_subdomain("sfbay")
        assert region1 is not None
        assert region1.subdomain == region2.subdomain
    
    def test_region_by_subdomain_not_found(self):
        """Return None for unknown subdomain."""
        region = region_by_subdomain("nonexistent")
        assert region is None
    
    def test_region_url_property(self):
        """Region URL property."""
        region = region_by_subdomain("losangeles")
        assert region is not None
        assert region.url == "https://losangeles.craigslist.org"
    
    def test_all_regions_have_valid_data(self):
        """All bundled regions have required fields."""
        regions = load_regions()
        for region in regions:
            assert region.subdomain, f"Missing subdomain in {region}"
            assert region.label, f"Missing label in {region}"
            assert isinstance(region.lat, (int, float)), f"Invalid lat in {region}"
            assert isinstance(region.lon, (int, float)), f"Invalid lon in {region}"
            assert isinstance(region.country, str), f"Invalid country in {region}"
            assert region.url.startswith("https://"), f"Invalid URL in {region}"
