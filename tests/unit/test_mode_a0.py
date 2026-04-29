"""Tests for Mode A0 (zero-cost API recipe extraction)."""

import pytest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from doormat.extraction.mode_a0 import run_mode_a0, _fire_recipe, _handle_recipe_failure
from doormat.extraction.schemas import ApiRecipe, ExtractedListing, ListingExtractionResult, PetsPolicy
from doormat.models.orm import ExtractionStrategy


def create_test_recipe(**overrides):
    """Create a test ApiRecipe with sensible defaults."""
    defaults = {
        "method": "GET",
        "url_template": "https://api.example.com/listings/{url}",
        "response_root": "listing",
        "field_paths": {
            "address": "$.address",
            "rent": "$.price",
            "bedrooms": "$.beds",
            "bathrooms": "$.baths",
        },
        "extractable_fields": ["address", "rent", "bedrooms", "bathrooms"],
        "captured_at": datetime.now(UTC),
        "captured_from_listing_id": "listing_123",
        "confidence": "high",
    }
    defaults.update(overrides)
    return ApiRecipe(**defaults)


class TestModeA0:
    """Test Mode A0 execution."""

    @pytest.mark.asyncio
    async def test_mode_a0_no_recipe(self):
        """Mode A0 returns None when strategy has no recipe."""
        strategy = MagicMock(spec=ExtractionStrategy)
        strategy.api_recipe = None
        
        http_client = AsyncMock()
        result = await run_mode_a0(
            url="https://example.com/listing/123",
            source_id="pm_test",
            strategy=strategy,
            http_client=http_client,
        )
        
        assert result is None
        http_client.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_mode_a0_no_strategy(self):
        """Mode A0 returns None when strategy is None."""
        http_client = AsyncMock()
        result = await run_mode_a0(
            url="https://example.com/listing/123",
            source_id="pm_test",
            strategy=None,
            http_client=http_client,
        )
        
        assert result is None
        http_client.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_mode_a0_low_confidence_recipe(self):
        """Mode A0 skips recipe with low confidence."""
        recipe = create_test_recipe(confidence="low")
        strategy = MagicMock(spec=ExtractionStrategy)
        strategy.api_recipe = recipe
        
        http_client = AsyncMock()
        result = await run_mode_a0(
            url="https://example.com/listing/123",
            source_id="pm_test",
            strategy=strategy,
            http_client=http_client,
        )
        
        assert result is None
        http_client.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_mode_a0_no_confidence_recipe(self):
        """Mode A0 skips recipe with no confidence (retired)."""
        recipe = create_test_recipe(confidence="high")
        recipe.confidence = None
        strategy = MagicMock(spec=ExtractionStrategy)
        strategy.api_recipe = recipe
        
        http_client = AsyncMock()
        result = await run_mode_a0(
            url="https://example.com/listing/123",
            source_id="pm_test",
            strategy=strategy,
            http_client=http_client,
        )
        
        assert result is None
        http_client.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_mode_a0_success(self):
        """Mode A0 successfully extracts via recipe."""
        recipe = create_test_recipe(failure_count=1)
        strategy = MagicMock(spec=ExtractionStrategy)
        strategy.api_recipe = recipe
        
        http_client = AsyncMock()
        http_client.request.return_value = MagicMock(
            json=lambda: {
                "listing": {
                    "address": "123 Main St",
                    "price": 2500,
                    "beds": 2,
                    "baths": 1,
                }
            },
            raise_for_status=lambda: None,
        )
        
        result = await run_mode_a0(
            url="https://example.com/listing/123",
            source_id="pm_test",
            strategy=strategy,
            http_client=http_client,
        )
        
        assert result is not None
        assert result.mode == "A"
        assert result.confidence == "high"
        assert result.listing.address == "123 Main St"
        assert result.listing.rent == 2500
        assert result.listing.bedrooms == 2
        assert result.listing.bathrooms == 1.0
        assert recipe.failure_count == 0
        assert recipe.last_failure_at is None

    @pytest.mark.asyncio
    async def test_mode_a0_http_error_increments_failure(self):
        """Mode A0 increments failure counter on HTTP error."""
        recipe = create_test_recipe(failure_count=0)
        strategy = MagicMock(spec=ExtractionStrategy)
        strategy.api_recipe = recipe
        
        http_client = AsyncMock()
        http_client.request.side_effect = httpx.HTTPError("Network timeout")
        
        result = await run_mode_a0(
            url="https://example.com/listing/123",
            source_id="pm_test",
            strategy=strategy,
            http_client=http_client,
        )
        
        assert result is None
        assert recipe.failure_count == 1
        assert recipe.last_failure_at is not None

    @pytest.mark.asyncio
    async def test_mode_a0_retire_after_3_failures(self):
        """Mode A0 retires recipe after 3 consecutive failures."""
        recipe = create_test_recipe(failure_count=2)
        strategy = MagicMock(spec=ExtractionStrategy)
        strategy.api_recipe = recipe
        
        http_client = AsyncMock()
        http_client.request.side_effect = httpx.HTTPError("Network timeout")
        
        result = await run_mode_a0(
            url="https://example.com/listing/123",
            source_id="pm_test",
            strategy=strategy,
            http_client=http_client,
        )
        
        assert result is None
        assert recipe.failure_count == 3
        assert recipe.confidence is None  # Retired


class TestFireRecipe:
    """Test HTTP recipe execution."""

    @pytest.mark.asyncio
    async def test_fire_recipe_simple(self):
        """_fire_recipe executes GET request and returns full response JSON."""
        recipe = create_test_recipe()
        
        http_client = AsyncMock()
        response_mock = MagicMock()
        response_mock.json.return_value = {
            "listing": {"address": "123 Main St"}
        }
        response_mock.raise_for_status.return_value = None
        http_client.request.return_value = response_mock
        
        result = await _fire_recipe(
            http_client,
            "https://example.com/listing/123",
            recipe,
        )
        
        # Should return the full response JSON, not navigate to response_root
        assert result == {"listing": {"address": "123 Main St"}}
        http_client.request.assert_called_once()
        call_kwargs = http_client.request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["url"] == "https://api.example.com/listings/https://example.com/listing/123"

    @pytest.mark.asyncio
    async def test_fire_recipe_with_response_root(self):
        """_fire_recipe returns full response JSON regardless of response_root."""
        recipe = create_test_recipe(response_root="data.property")
        
        http_client = AsyncMock()
        response_mock = MagicMock()
        response_mock.json.return_value = {
            "data": {
                "property": {"address": "456 Oak St"}
            }
        }
        response_mock.raise_for_status.return_value = None
        http_client.request.return_value = response_mock
        
        result = await _fire_recipe(
            http_client,
            "https://example.com/listing/456",
            recipe,
        )
        
        # Should return the full response JSON; extract_listing_via_recipe handles navigation
        assert result == {"data": {"property": {"address": "456 Oak St"}}}

    @pytest.mark.asyncio
    async def test_fire_recipe_http_error_returns_none(self):
        """_fire_recipe returns None on HTTP error."""
        recipe = create_test_recipe()
        
        http_client = AsyncMock()
        http_client.request.side_effect = httpx.HTTPError("Network timeout")
        
        result = await _fire_recipe(
            http_client,
            "https://example.com/listing/123",
            recipe,
        )
        
        assert result is None

    @pytest.mark.asyncio
    async def test_fire_recipe_invalid_json_returns_none(self):
        """_fire_recipe returns None if response is not valid JSON."""
        recipe = create_test_recipe()
        
        http_client = AsyncMock()
        response_mock = MagicMock()
        response_mock.json.side_effect = ValueError("Invalid JSON")
        response_mock.raise_for_status.return_value = None
        http_client.request.return_value = response_mock
        
        result = await _fire_recipe(
            http_client,
            "https://example.com/listing/123",
            recipe,
        )
        
        assert result is None


class TestHandleRecipeFailure:
    """Test failure handling and retirement logic."""

    def test_handle_recipe_failure_increments_counter(self):
        """_handle_recipe_failure increments failure_count."""
        recipe = create_test_recipe(failure_count=0)
        
        result = _handle_recipe_failure(recipe)
        
        assert result is None
        assert recipe.failure_count == 1
        assert recipe.last_failure_at is not None

    def test_handle_recipe_failure_retires_at_3(self):
        """_handle_recipe_failure retires recipe at 3 failures."""
        recipe = create_test_recipe(failure_count=2)
        
        result = _handle_recipe_failure(recipe)
        
        assert result is None
        assert recipe.failure_count == 3
        assert recipe.confidence is None  # Retired

    def test_handle_recipe_failure_with_zero_counter(self):
        """_handle_recipe_failure handles zero failure_count gracefully."""
        recipe = create_test_recipe(failure_count=0)
        
        result = _handle_recipe_failure(recipe)
        
        assert result is None
        assert recipe.failure_count == 1
