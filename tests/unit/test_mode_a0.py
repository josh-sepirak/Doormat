"""Tests for Mode A0 (zero-cost API recipe extraction)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from doormat.db.base import AsyncSessionLocal
from doormat.extraction.mode_a0 import _fire_recipe, _handle_recipe_failure, run_mode_a0
from doormat.extraction.schemas import (
    ApiRecipe,
)
from doormat.models.orm import ExtractionStrategy, PropertyManager


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

    @pytest.mark.asyncio
    async def test_mode_a0_real_orm_failures_accumulate_and_retire(self):
        """Real ORM ExtractionStrategy persists failure counts and retires after 3 failures."""
        pm_id = f"pm_{uuid.uuid4().hex[:8]}"
        strat_id = f"strat_{uuid.uuid4().hex[:8]}"

        async with AsyncSessionLocal() as session:
            pm = PropertyManager(
                id=pm_id,
                name="Test PM",
                city="San Francisco",
                website="https://example.com",
            )
            strategy = ExtractionStrategy(
                id=strat_id,
                property_manager_id=pm_id,
                strategy_json="{}",
                api_recipe=create_test_recipe(confidence="high", failure_count=0),
            )
            session.add_all([pm, strategy])
            await session.commit()

        # Execute 3 failing runs
        http_client = AsyncMock()
        http_client.request.side_effect = httpx.ConnectError("Connection refused")

        async with AsyncSessionLocal() as session:
            strat = await session.get(ExtractionStrategy, strat_id)
            assert strat is not None
            assert strat.api_recipe is not None
            assert strat.api_recipe.failure_count == 0

            # 1st failure
            res1 = await run_mode_a0("https://example.com/1", pm_id, strat, http_client)
            assert res1 is None
            assert strat.api_recipe.failure_count == 1
            await session.commit()

            # 2nd failure
            res2 = await run_mode_a0("https://example.com/2", pm_id, strat, http_client)
            assert res2 is None
            assert strat.api_recipe.failure_count == 2
            await session.commit()

            # 3rd failure - should retire recipe
            res3 = await run_mode_a0("https://example.com/3", pm_id, strat, http_client)
            assert res3 is None
            assert strat.api_recipe.failure_count == 3
            assert strat.api_recipe.confidence is None
            await session.commit()

        # Reload in a completely new session from database
        async with AsyncSessionLocal() as session:
            reloaded = await session.get(ExtractionStrategy, strat_id)
            assert reloaded is not None
            assert reloaded.api_recipe is not None
            assert reloaded.api_recipe.failure_count == 3
            assert reloaded.api_recipe.confidence is None

            # 4th attempt: should skip immediately due to retired recipe
            http_client.reset_mock()
            res4 = await run_mode_a0("https://example.com/4", pm_id, reloaded, http_client)
            assert res4 is None
            http_client.request.assert_not_called()


class TestFireRecipe:
    """Test HTTP recipe execution."""

    @pytest.mark.asyncio
    async def test_fire_recipe_simple(self):
        """_fire_recipe executes GET request and returns full response JSON."""
        recipe = create_test_recipe()

        http_client = AsyncMock()
        response_mock = MagicMock()
        response_mock.json.return_value = {"listing": {"address": "123 Main St"}}
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
        assert (
            call_kwargs["url"] == "https://api.example.com/listings/https://example.com/listing/123"
        )

    @pytest.mark.asyncio
    async def test_fire_recipe_with_response_root(self):
        """_fire_recipe returns full response JSON regardless of response_root."""
        recipe = create_test_recipe(response_root="data.property")

        http_client = AsyncMock()
        response_mock = MagicMock()
        response_mock.json.return_value = {"data": {"property": {"address": "456 Oak St"}}}
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
