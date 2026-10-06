"""Unit tests for recipe executor and validator."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import httpx
import pytest

from doormat.extraction.recipe_executor import (
    _coerce_pets_policy,
    _tokenize_path,
    _walk_path,
    extract_listing_via_recipe,
)
from doormat.extraction.recipe_validator import (
    RecipeValidator,
    _addresses_match,
)
from doormat.extraction.schemas import ApiRecipe, ExtractedListing
from doormat.schemas import PetsPolicy


class TestRecipeExecutor:
    """Tests for extract_listing_via_recipe."""

    def test_extract_simple_listing(self):
        """Extract listing from flat JSON object."""
        recipe = ApiRecipe(
            method="GET",
            url_template="https://api.example.com/listings/{listing_id}",
            response_root="$",
            field_paths={
                "address": "address",
                "rent": "price",
                "bedrooms": "beds",
                "bathrooms": "baths",
            },
            extractable_fields=["address", "rent", "bedrooms", "bathrooms"],
            captured_at=datetime.now(UTC),
            captured_from_listing_id="123",
            confidence="high",
        )
        response = {
            "address": "123 Main St, SF, CA",
            "price": 3200,
            "beds": 2,
            "baths": 1.0,
            "description": "Nice apartment",
        }
        listing = extract_listing_via_recipe(recipe, response)
        assert listing.address == "123 Main St, SF, CA"
        assert listing.rent == 3200
        assert listing.bedrooms == 2
        assert listing.bathrooms == 1.0

    def test_extract_nested_response_root(self):
        """Extract from nested response using $.data.listing."""
        recipe = ApiRecipe(
            method="GET",
            url_template="https://api.example.com/listings/{listing_id}",
            response_root="$.data.listing",
            field_paths={
                "address": "address",
                "rent": "price",
                "bedrooms": "beds",
                "bathrooms": "baths",
            },
            extractable_fields=["address", "rent", "bedrooms", "bathrooms"],
            captured_at=datetime.now(UTC),
            captured_from_listing_id="123",
            confidence="high",
        )
        response = {
            "data": {
                "listing": {
                    "address": "456 Oak Ave",
                    "price": 2800,
                    "beds": 1,
                    "baths": 1.0,
                }
            }
        }
        listing = extract_listing_via_recipe(recipe, response)
        assert listing.address == "456 Oak Ave"
        assert listing.rent == 2800

    def test_extract_array_index_response_root(self):
        """Extract from array using $.results[0]."""
        recipe = ApiRecipe(
            method="GET",
            url_template="https://api.example.com/listings",
            response_root="$.results[0]",
            field_paths={
                "address": "address",
                "rent": "monthly_rent",
                "bedrooms": "num_beds",
                "bathrooms": "num_baths",
            },
            extractable_fields=["address", "rent", "bedrooms", "bathrooms"],
            captured_at=datetime.now(UTC),
            captured_from_listing_id="789",
            confidence="high",
        )
        response = {
            "results": [
                {
                    "address": "789 Pine St",
                    "monthly_rent": 3500,
                    "num_beds": 3,
                    "num_baths": 2.0,
                }
            ]
        }
        listing = extract_listing_via_recipe(recipe, response)
        assert listing.address == "789 Pine St"
        assert listing.bedrooms == 3

    def test_extract_missing_required_field_raises(self):
        """Raise ValueError when a required field is missing."""
        recipe = ApiRecipe(
            method="GET",
            url_template="https://api.example.com/listings/{listing_id}",
            response_root="$",
            field_paths={
                "address": "address",
                "rent": "price",
                "bedrooms": "beds",
                "bathrooms": "baths",
            },
            extractable_fields=["address", "rent", "bedrooms", "bathrooms"],
            captured_at=datetime.now(UTC),
            captured_from_listing_id="123",
            confidence="high",
        )
        response = {
            "address": "123 Main St",
            # missing price
            "beds": 2,
            "baths": 1.0,
        }
        with pytest.raises(ValueError, match="required field 'rent'"):
            extract_listing_via_recipe(recipe, response)

    def test_extract_optional_fields(self):
        """Optional fields like sqft and amenities are handled gracefully."""
        recipe = ApiRecipe(
            method="GET",
            url_template="https://api.example.com/listings/{listing_id}",
            response_root="$",
            field_paths={
                "address": "address",
                "rent": "price",
                "bedrooms": "beds",
                "bathrooms": "baths",
                "sqft": "size",
                "amenities": "tags",
            },
            extractable_fields=["address", "rent", "bedrooms", "bathrooms", "sqft", "amenities"],
            captured_at=datetime.now(UTC),
            captured_from_listing_id="123",
            confidence="high",
        )
        response = {
            "address": "123 Main St",
            "price": 2500,
            "beds": 1,
            "baths": 1.0,
            "size": 750,
            "tags": ["pool", "gym"],
        }
        listing = extract_listing_via_recipe(recipe, response)
        assert listing.sqft == 750
        assert listing.amenities == ["pool", "gym"]

    def test_extract_pets_policy_coercion(self):
        """Test pets_policy field coercion from string."""
        recipe = ApiRecipe(
            method="GET",
            url_template="https://api.example.com/listings/{listing_id}",
            response_root="$",
            field_paths={
                "address": "address",
                "rent": "price",
                "bedrooms": "beds",
                "bathrooms": "baths",
                "pets_policy": "pets",
            },
            extractable_fields=["address", "rent", "bedrooms", "bathrooms", "pets_policy"],
            captured_at=datetime.now(UTC),
            captured_from_listing_id="123",
            confidence="high",
        )
        response = {
            "address": "123 Main St",
            "price": 2500,
            "beds": 1,
            "baths": 1.0,
            "pets": "Dogs allowed, cats allowed",
        }
        listing = extract_listing_via_recipe(recipe, response)
        assert listing.pets_policy in [
            PetsPolicy.ALLOWED_WITH_SMALL_DOG,
            PetsPolicy.UNKNOWN,
        ]


class TestWalkPath:
    """Tests for _walk_path."""

    def test_root_path(self):
        """$ returns the entire object."""
        obj = {"a": 1, "b": 2}
        assert _walk_path(obj, "$") == obj
        assert _walk_path(obj, "") == obj

    def test_simple_key(self):
        """$.key retrieves a value."""
        obj = {"a": 1, "b": {"c": 2}}
        assert _walk_path(obj, "$.a") == 1
        assert _walk_path(obj, "a") == 1

    def test_nested_key(self):
        """$.a.b.c navigates nested dicts."""
        obj = {"a": {"b": {"c": 42}}}
        assert _walk_path(obj, "$.a.b.c") == 42

    def test_array_index(self):
        """$.a[0] accesses array elements."""
        obj = {"a": [10, 20, 30]}
        assert _walk_path(obj, "$.a[0]") == 10
        assert _walk_path(obj, "a[1]") == 20

    def test_mixed_navigation(self):
        """$.data.items[0].name combines dict and array."""
        obj = {"data": {"items": [{"name": "Alice"}, {"name": "Bob"}]}}
        assert _walk_path(obj, "$.data.items[0].name") == "Alice"
        assert _walk_path(obj, "data.items[1].name") == "Bob"

    def test_missing_path_returns_none(self):
        """Missing keys or out-of-bounds indices return None."""
        obj = {"a": {"b": [1, 2]}}
        assert _walk_path(obj, "$.missing") is None
        assert _walk_path(obj, "$.a.missing.c") is None
        assert _walk_path(obj, "$.a.b[10]") is None


class TestTokenizePath:
    """Tests for _tokenize_path."""

    def test_simple_dot_notation(self):
        """data.listings.name → ['data', 'listings', 'name']"""
        assert _tokenize_path("data.listings.name") == ["data", "listings", "name"]

    def test_array_indices(self):
        """data.items[0].name → ['data', 'items', 0, 'name']"""
        assert _tokenize_path("data.items[0].name") == ["data", "items", 0, "name"]

    def test_multiple_indices(self):
        """matrix[0][1] → [matrix, 0, 1]"""
        assert _tokenize_path("matrix[0][1]") == ["matrix", 0, 1]


class TestCoercePetsPolicy:
    """Tests for _coerce_pets_policy."""

    def test_coerce_none_allowed(self):
        policy = _coerce_pets_policy("no pets allowed")
        assert policy == PetsPolicy.NONE_ALLOWED

    def test_coerce_cats_only(self):
        policy = _coerce_pets_policy("cats only")
        assert policy == PetsPolicy.CATS_ONLY

    def test_coerce_allowed_with_small_dog(self):
        policy = _coerce_pets_policy("small dogs welcome")
        assert policy == PetsPolicy.ALLOWED_WITH_SMALL_DOG

    def test_coerce_unknown(self):
        policy = _coerce_pets_policy("exotic pets")
        assert policy == PetsPolicy.UNKNOWN

    def test_coerce_enum_passthrough(self):
        """If already an enum, return as-is."""
        policy = _coerce_pets_policy(PetsPolicy.CATS_ONLY)
        assert policy == PetsPolicy.CATS_ONLY


class TestAddressMatch:
    """Tests for _addresses_match."""

    def test_exact_match(self):
        assert _addresses_match("123 Main St", "123 Main St")

    def test_substring_match(self):
        """Shorter address is substring of longer."""
        assert _addresses_match("123 Main", "123 Main St, SF, CA")
        assert _addresses_match("123 Main St, SF, CA", "123 Main")

    def test_case_insensitive(self):
        assert _addresses_match("123 MAIN ST", "123 main st")

    def test_punctuation_ignored(self):
        assert _addresses_match("123 Main St.", "123 Main St")

    def test_mismatch(self):
        """Different addresses don't match."""
        assert not _addresses_match("123 Main St", "456 Oak Ave")

    def test_empty_addresses(self):
        """Empty or None-like addresses don't match."""
        assert not _addresses_match("", "123 Main St")
        assert not _addresses_match("123 Main St", "")


class TestRecipeValidator:
    """Tests for RecipeValidator."""

    @pytest.mark.asyncio
    async def test_self_replay_success(self):
        """Self-replay succeeds with confidence='medium'."""
        client = AsyncMock(spec=httpx.AsyncClient)
        client.request.return_value = httpx.Response(
            200,
            json={
                "address": "123 Main St",
                "price": 2500,
                "beds": 1,
                "baths": 1.0,
            },
        )

        recipe = ApiRecipe(
            method="GET",
            url_template="https://api.example.com/listings/{listing_id}",
            response_root="$",
            field_paths={
                "address": "address",
                "rent": "price",
                "bedrooms": "beds",
                "bathrooms": "baths",
            },
            extractable_fields=["address", "rent", "bedrooms", "bathrooms"],
            captured_at=datetime.now(UTC),
            captured_from_listing_id="123",
            confidence="low",
        )

        validator = RecipeValidator(client)
        result = await validator.validate(recipe, [])

        assert result.valid
        assert result.confidence == "medium"
        assert "self-replay succeeded" in result.reason

    @pytest.mark.asyncio
    async def test_held_out_replay_success(self):
        """Replay against held-out listing succeeds with confidence='high'."""
        client = AsyncMock(spec=httpx.AsyncClient)
        client.request.return_value = httpx.Response(
            200,
            json={
                "address": "456 Oak Ave",
                "price": 2800,
                "beds": 1,
                "baths": 1.0,
            },
        )

        recipe = ApiRecipe(
            method="GET",
            url_template="https://api.example.com/listings/{listing_id}",
            response_root="$",
            field_paths={
                "address": "address",
                "rent": "price",
                "bedrooms": "beds",
                "bathrooms": "baths",
            },
            extractable_fields=["address", "rent", "bedrooms", "bathrooms"],
            captured_at=datetime.now(UTC),
            captured_from_listing_id="123",
            confidence="low",
        )

        expected_listing = ExtractedListing(
            address="456 Oak Ave",
            rent=2800,
            bedrooms=1,
            bathrooms=1.0,
            pets_policy=PetsPolicy.UNKNOWN,
            amenities=[],
            photos=[],
            description="",
        )

        validator = RecipeValidator(client)
        result = await validator.validate(recipe, [("456", expected_listing)])

        assert result.valid
        assert result.confidence == "high"
        assert "matched" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_held_out_replay_address_mismatch(self):
        """Replay fails when address doesn't match expected."""
        client = AsyncMock(spec=httpx.AsyncClient)
        client.request.return_value = httpx.Response(
            200,
            json={
                "address": "999 Wrong St",
                "price": 2800,
                "beds": 1,
                "baths": 1.0,
            },
        )

        recipe = ApiRecipe(
            method="GET",
            url_template="https://api.example.com/listings/{listing_id}",
            response_root="$",
            field_paths={
                "address": "address",
                "rent": "price",
                "bedrooms": "beds",
                "bathrooms": "baths",
            },
            extractable_fields=["address", "rent", "bedrooms", "bathrooms"],
            captured_at=datetime.now(UTC),
            captured_from_listing_id="123",
            confidence="low",
        )

        expected_listing = ExtractedListing(
            address="456 Oak Ave",
            rent=2800,
            bedrooms=1,
            bathrooms=1.0,
            pets_policy=PetsPolicy.UNKNOWN,
            amenities=[],
            photos=[],
            description="",
        )

        validator = RecipeValidator(client)
        result = await validator.validate(recipe, [("456", expected_listing)])

        assert not result.valid
        assert result.confidence == "low"
        assert "address mismatch" in result.reason

    @pytest.mark.asyncio
    async def test_replay_http_error_fails(self):
        """HTTP errors cause validation to fail with confidence='low'."""
        client = AsyncMock(spec=httpx.AsyncClient)
        client.request.side_effect = httpx.ConnectError("Connection refused")

        recipe = ApiRecipe(
            method="GET",
            url_template="https://api.example.com/listings/{listing_id}",
            response_root="$",
            field_paths={
                "address": "address",
                "rent": "price",
                "bedrooms": "beds",
                "bathrooms": "baths",
            },
            extractable_fields=["address", "rent", "bedrooms", "bathrooms"],
            captured_at=datetime.now(UTC),
            captured_from_listing_id="123",
            confidence="low",
        )

        validator = RecipeValidator(client)
        result = await validator.validate(recipe, [])

        assert not result.valid
        assert result.confidence == "low"
