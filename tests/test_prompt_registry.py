"""Tests for LLM prompt registry merge and validation."""

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from doormat.llm.prompt_registry import (
    PromptKey,
    merge_overrides,
    parse_prompt_overrides,
    validate_override,
)
from doormat.models.orm import Preference


def _pref(overrides: str | dict | None = None) -> Preference:
    now = datetime.now(UTC)
    return Preference(
        id="p1",
        description="x" * 15,
        city="Austin",
        prompt_overrides=overrides,
        created_at=now,
        updated_at=now,
    )


def test_parse_prompt_overrides_empty():
    assert parse_prompt_overrides(None) == {}
    p = _pref(None)
    assert parse_prompt_overrides(p) == {}


def test_merge_reset_all():
    base = {"scoring_system": "custom"}
    out = merge_overrides(base, patch=None, reset_keys=None, reset_all=True)
    assert out == {}


def test_merge_patch_and_reset_key():
    base = {"scoring_system": "a", "discovery_search_system": "b"}
    out = merge_overrides(
        base,
        patch={"scoring_system": "new"},
        reset_keys=["discovery_search_system"],
        reset_all=False,
    )
    assert out == {"scoring_system": "new"}


def test_validate_override_too_long():
    with pytest.raises(HTTPException) as ei:
        validate_override(PromptKey.SCORING_SYSTEM, "x" * 20_000)
    assert ei.value.status_code == 422


def test_validate_mode_a_user_requires_placeholders():
    bad = "no placeholders here"
    with pytest.raises(HTTPException):
        validate_override(PromptKey.EXTRACTION_MODE_A_USER, bad)
