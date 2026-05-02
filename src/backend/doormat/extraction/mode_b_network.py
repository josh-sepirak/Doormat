"""Attach CDP network listeners to Browser-Use for Mode B JSON capture."""

from __future__ import annotations

import asyncio
import functools
import time
from typing import Any, Optional
from urllib.parse import urlparse

import structlog

from doormat.extraction.network_capture import NetworkCapture, decode_cdp_response_body

logger = structlog.get_logger(__name__)

# Avoid buffering huge bodies in memory during extraction
_MAX_BODY_CHARS = 500_000


def _normalize_cdp_headers(raw: Any) -> dict[str, str]:
    """Turn CDP header representation into a flat str->str dict."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    if isinstance(raw, list):
        out: dict[str, str] = {}
        for item in raw:
            if isinstance(item, dict) and "name" in item and "value" in item:
                out[str(item["name"])] = str(item["value"])
        return out
    return {}


def _host_allowed(url: str, allowed_host: str) -> bool:
    try:
        return urlparse(url).netloc.lower() == allowed_host.lower()
    except Exception:
        return False


async def _cdp_on_request_will_be_sent(
    params: dict[str, Any],
    session_id: Optional[str],
    *,
    capture: NetworkCapture,
    allowed_host: str,
) -> None:
    del session_id  # unused
    if not capture.enabled:
        return
    rid = params.get("requestId")
    req = params.get("request") or {}
    url = str(req.get("url") or "")
    if not _host_allowed(url, allowed_host):
        return
    method = str(req.get("method") or "GET")
    headers = _normalize_cdp_headers(req.get("headers"))
    post = req.get("postData")
    post_data = str(post) if post is not None else None
    ts = float(params.get("timestamp") or 0.0)
    if not rid:
        return
    capture.record_cdp_request(
        str(rid),
        method,
        url,
        headers,
        post_data,
        timestamp=ts,
    )


async def _cdp_on_response_received(
    params: dict[str, Any],
    session_id: Optional[str],
    *,
    capture: NetworkCapture,
) -> None:
    del session_id  # unused
    if not capture.enabled:
        return
    rid = params.get("requestId")
    if not rid:
        return
    resp = params.get("response") or {}
    status = int(resp.get("status") or 0)
    headers = _normalize_cdp_headers(resp.get("headers"))
    mime = str(resp.get("mimeType") or "")
    ts = float(params.get("timestamp") or 0.0)
    capture.record_cdp_response_meta(
        str(rid),
        status,
        headers,
        mime_type=mime,
        timestamp=ts,
    )


async def _cdp_on_loading_finished(
    params: dict[str, Any],
    session_id: Optional[str],
    *,
    capture: NetworkCapture,
    allowed_host: str,
    client: Any,
) -> None:
    if not capture.enabled:
        return
    rid = params.get("requestId")
    if not rid:
        return
    call = capture.get_cdp_call(str(rid))
    if call is None or not _host_allowed(call.request.url, allowed_host):
        return
    try:
        result = await client.send.Network.getResponseBody(
            params={"requestId": rid},
            session_id=session_id,
        )
        body = decode_cdp_response_body(
            str(result.get("body") or ""),
            bool(result.get("base64Encoded")),
        )
        if len(body) > _MAX_BODY_CHARS:
            body = body[:_MAX_BODY_CHARS]
        capture.set_cdp_response_body(str(rid), body)
    except Exception as exc:
        logger.debug(
            "mode_b_network_get_response_body_failed",
            request_id=str(rid),
            error_type=type(exc).__name__,
        )


async def install_mode_b_network_handlers(
    browser_session: Any,
    capture: NetworkCapture,
    allowed_host: str,
) -> None:
    """Register Network.* CDP handlers on the session's root CDP client.

    SessionManager already calls Network.enable per page; we only subscribe to events.
    """
    client = browser_session.cdp_client
    reg = client.register.Network

    reg.requestWillBeSent(
        functools.partial(
            _cdp_on_request_will_be_sent,
            capture=capture,
            allowed_host=allowed_host,
        )
    )
    reg.responseReceived(functools.partial(_cdp_on_response_received, capture=capture))
    reg.loadingFinished(
        functools.partial(
            _cdp_on_loading_finished,
            capture=capture,
            allowed_host=allowed_host,
            client=client,
        )
    )
    logger.info("mode_b_network_handlers_installed", host=allowed_host)


async def wait_install_mode_b_network_capture(
    browser_session: Any,
    capture: NetworkCapture,
    listing_url: str,
    *,
    timeout_s: Optional[float] = None,
    poll_s: float = 0.05,
) -> bool:
    """Wait for CDP, then start capture and install handlers. Returns True if installed."""
    from doormat.config import settings

    if timeout_s is None:
        timeout_s = settings.MODE_B_NETWORK_CAPTURE_WAIT_S

    host = urlparse(listing_url).netloc
    if not host:
        return False
    deadline = time.monotonic() + timeout_s
    is_conn = getattr(browser_session, "is_cdp_connected", None)
    if not callable(is_conn):
        logger.debug("mode_b_network_skip_no_cdp_hook")
        return False

    while time.monotonic() < deadline:
        if is_conn():
            try:
                capture.start()
                await install_mode_b_network_handlers(browser_session, capture, host)
                return True
            except Exception as exc:
                logger.warning(
                    "mode_b_network_install_failed",
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
                capture.stop()
                return False
        await asyncio.sleep(poll_s)
    logger.warning("mode_b_network_install_timeout", host=host)
    return False
