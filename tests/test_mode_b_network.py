"""Tests for Mode B CDP network capture helpers."""

import pytest

from doormat.extraction.network_capture import NetworkCapture, decode_cdp_response_body


def test_decode_cdp_response_body_base64() -> None:
    import base64

    raw = '{"a": 1}'
    b64 = base64.b64encode(raw.encode()).decode("ascii")
    assert decode_cdp_response_body(b64, True) == raw


def test_network_capture_cdp_correlation_and_listing_heuristic() -> None:
    cap = NetworkCapture()
    cap.start()
    cap.record_cdp_request(
        "req-1",
        "GET",
        "https://pm.example.com/api/listings/1",
        {"accept": "application/json"},
        None,
        0.0,
    )
    cap.record_cdp_response_meta(
        "req-1",
        200,
        {"content-type": "application/json"},
        mime_type="application/json",
    )
    body = (
        '{"address": "1 Main St", "rent": 2000, "bedrooms": 2, '
        '"bathrooms": 1, "property": {"id": 1}, "listing": true}'
    )
    cap.set_cdp_response_body("req-1", body)
    cap.stop()

    candidates = cap.get_listing_candidates()
    assert len(candidates) == 1
    assert candidates[0].request.url.endswith("/api/listings/1")


@pytest.mark.asyncio
async def test_wait_install_skips_without_is_cdp_connected() -> None:
    from doormat.extraction.mode_b_network import wait_install_mode_b_network_capture

    class S:
        pass

    cap = NetworkCapture()
    ok = await wait_install_mode_b_network_capture(S(), cap, "https://example.com/x")
    assert ok is False
