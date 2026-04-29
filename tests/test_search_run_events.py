"""Tests for search run event helpers and diagnostic sanitization (T008, T032)."""

from doormat.runs.events import sanitize_diagnostic_payload


def test_sanitize_strips_secret_like_keys():
    raw = {
        "openrouter_api_key": "sk-secret",
        "nested": {"bearer_token": "abc", "safe": "ok"},
        "html": "x" * 3000,
    }
    out = sanitize_diagnostic_payload(raw)
    assert out["openrouter_api_key"] == "[redacted]"
    assert out["nested"]["bearer_token"] == "[redacted]"
    assert out["nested"]["safe"] == "ok"
    assert isinstance(out["html"], str)
    assert len(out["html"]) < 600


def test_sanitize_truncates_long_strings():
    s = "a" * 5000
    out = sanitize_diagnostic_payload({"msg": s})
    assert len(out["msg"]) < 2100
