"""Network capture for CDP to intercept JSON API calls during Mode B extraction."""

import base64
import json
from dataclasses import dataclass, field
from typing import Any, Optional, cast

import structlog

logger = structlog.get_logger(__name__)

# Sensitive headers to scrub before storing (auth tokens, cookies, etc.)
SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-csrf-token",
    "x-api-key",
    "x-auth-token",
    "x-access-token",
    "bearer",
    "token",
    "authentication",
    "x-amzn-authorization",
    "x-goog-maps-api-client",
}


@dataclass
class NetworkRequest:
    """A captured HTTP request."""

    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None


@dataclass
class NetworkResponse:
    """A captured HTTP response."""

    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None
    is_json: bool = False


@dataclass
class CapturedNetworkCall:
    """A complete request/response pair from the network."""

    request: NetworkRequest
    response: NetworkResponse
    timestamp: float = 0.0
    request_id: Optional[str] = None
    """Chrome DevTools requestId when captured via CDP."""

    @property
    def response_json(self) -> Optional[dict[str, Any]]:
        """Parse response body as JSON if possible."""
        if not self.response.is_json or not self.response.body:
            return None
        try:
            return cast(dict[str, Any], json.loads(self.response.body))
        except (json.JSONDecodeError, ValueError):
            return None

    @property
    def is_api_call(self) -> bool:
        """Check if this looks like a JSON API call (not HTML/CSS/JS)."""
        return (
            self.response.is_json
            and self.response.status_code == 200
            and self.response.body is not None
            and len(self.response.body) > 10
        )


class NetworkCapture:
    """Buffer for captured network calls during Mode B extraction.

    Listens to CDP network events, filters to JSON responses, scrubs sensitive
    headers, and provides a list of candidates for recipe synthesis.
    """

    def __init__(self) -> None:
        """Initialize the network capture buffer."""
        self.calls: list[CapturedNetworkCall] = []
        self.enabled = False
        self._cdp_index: dict[str, int] = {}

    def start(self) -> None:
        """Begin capturing network traffic."""
        self.calls = []
        self._cdp_index = {}
        self.enabled = True
        logger.debug("network_capture_started")

    def stop(self) -> None:
        """Stop capturing network traffic."""
        self.enabled = False
        logger.debug(
            "network_capture_stopped",
            total_calls=len(self.calls),
            api_calls=sum(1 for c in self.calls if c.is_api_call),
        )

    def record_cdp_request(
        self,
        request_id: str,
        method: str,
        url: str,
        headers: Optional[dict[str, str]] = None,
        post_data: Optional[str] = None,
        timestamp: float = 0.0,
    ) -> None:
        """Record a request from CDP Network.requestWillBeSent (request-id correlation)."""
        if not self.enabled:
            return
        scrubbed_headers = _scrub_headers(dict(headers or {}))
        req = NetworkRequest(
            method=method,
            url=url,
            headers=scrubbed_headers,
            body=post_data,
        )
        call = CapturedNetworkCall(
            request=req,
            response=NetworkResponse(status_code=0),
            timestamp=timestamp,
            request_id=request_id,
        )
        idx = len(self.calls)
        self.calls.append(call)
        self._cdp_index[request_id] = idx

    def record_cdp_response_meta(
        self,
        request_id: str,
        status_code: int,
        headers: Optional[dict[str, str]] = None,
        mime_type: str = "",
        timestamp: float = 0.0,
    ) -> None:
        """Fill status / headers / JSON hint from Network.responseReceived."""
        if not self.enabled:
            return
        idx = self._cdp_index.get(request_id)
        if idx is None:
            return
        call = self.calls[idx]
        is_json = "application/json" in (mime_type or "").lower()
        scrubbed = _scrub_headers(dict(headers or {}))
        call.response = NetworkResponse(
            status_code=status_code,
            headers=scrubbed,
            body=call.response.body,
            is_json=is_json,
        )
        call.timestamp = timestamp

    def set_cdp_response_body(self, request_id: str, body: str) -> None:
        """Attach response body after Network.getResponseBody (loading finished)."""
        if not self.enabled:
            return
        idx = self._cdp_index.get(request_id)
        if idx is None:
            return
        call = self.calls[idx]
        call.response.body = body

    def get_cdp_call(self, request_id: str) -> Optional["CapturedNetworkCall"]:
        """Return the in-flight capture row for a CDP request id, if any."""
        idx = self._cdp_index.get(request_id)
        if idx is None:
            return None
        return self.calls[idx]

    def record_request(
        self,
        method: str,
        url: str,
        headers: Optional[dict[str, str]] = None,
        body: Optional[str] = None,
        timestamp: float = 0.0,
    ) -> None:
        """Record an outgoing HTTP request."""
        if not self.enabled:
            return

        # Scrub sensitive headers
        scrubbed_headers = _scrub_headers(headers or {})

        request = NetworkRequest(
            method=method,
            url=url,
            headers=scrubbed_headers,
            body=body,
        )

        # Create a placeholder response (will be filled in by record_response)
        call = CapturedNetworkCall(
            request=request,
            response=NetworkResponse(status_code=0),
            timestamp=timestamp,
        )
        self.calls.append(call)

    def record_response(
        self,
        url: str,
        status_code: int,
        headers: Optional[dict[str, str]] = None,
        body: Optional[str] = None,
        timestamp: float = 0.0,
    ) -> None:
        """Record an incoming HTTP response (matched by URL)."""
        if not self.enabled:
            return

        # Find the corresponding request
        call = None
        for c in reversed(self.calls):
            if c.request.url == url:
                call = c
                break

        if not call:
            logger.debug("network_capture_response_no_request", url=url)
            return

        # Determine if response is JSON
        content_type = ""
        response_headers = headers or {}
        for key, value in response_headers.items():
            if key.lower() == "content-type":
                content_type = value.lower()
                break

        is_json = "application/json" in content_type

        # Scrub sensitive response headers
        scrubbed_headers = _scrub_headers(response_headers)

        call.response = NetworkResponse(
            status_code=status_code,
            headers=scrubbed_headers,
            body=body,
            is_json=is_json,
        )
        call.timestamp = timestamp

    def get_json_api_calls(self) -> list[CapturedNetworkCall]:
        """Return all captured JSON API calls (filtered by success and content type)."""
        return [c for c in self.calls if c.is_api_call]

    def get_listing_candidates(self) -> list[CapturedNetworkCall]:
        """Return API calls that might contain listing data.

        Heuristics:
        - Response body contains common listing field names
        - Response body is a JSON object or contains objects (not bare arrays)
        """
        candidates = []
        listing_keywords = {
            "address",
            "rent",
            "price",
            "bedrooms",
            "beds",
            "bathrooms",
            "baths",
            "listing",
            "property",
        }

        for call in self.get_json_api_calls():
            response_json = call.response_json
            if not response_json:
                continue

            # Convert to string for keyword matching
            response_str = json.dumps(response_json).lower()

            # Count matching keywords
            matches = sum(1 for keyword in listing_keywords if keyword in response_str)

            # If at least 3 keywords match, consider it a candidate
            if matches >= 3:
                candidates.append(call)

        return candidates


def decode_cdp_response_body(body: str, base64_encoded: bool) -> str:
    """Decode Network.getResponseBody payload (plain or base64)."""
    if base64_encoded:
        raw = base64.b64decode(body)
        return raw.decode("utf-8", errors="replace")
    return body


def _scrub_headers(headers: dict[str, str]) -> dict[str, str]:
    """Remove sensitive headers from a header dict.

    Args:
        headers: Original headers dict.

    Returns:
        New dict with sensitive headers removed.
    """
    scrubbed = {}
    for key, value in headers.items():
        if key.lower() not in SENSITIVE_HEADERS:
            scrubbed[key] = value
        else:
            scrubbed[key] = "[REDACTED]"
    return scrubbed


class CDPCapturer:
    """Bridge between Browser-Use CDP events and NetworkCapture.

    Converts Browser-Use network events into CapturedNetworkCall records.
    Handles event type detection and timing.
    """

    def __init__(self, capture: NetworkCapture):
        """Initialize the CDP capturer.

        Args:
            capture: NetworkCapture instance to record events into.
        """
        self.capture = capture
        self._pending_requests: dict[str, float] = {}

    def on_request_sent(
        self,
        request_id: str,
        method: str,
        url: str,
        headers: Optional[dict[str, str]] = None,
        post_data: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        """Handle request.Will Be Sent CDP event.

        Args:
            request_id: Unique ID for this request (from CDP).
            method: HTTP method (GET, POST, etc.).
            url: Request URL.
            headers: Request headers (may include sensitive auth).
            post_data: Request body (for POST/PUT requests).
            timestamp: Event timestamp (for sequencing).
        """
        if not self.capture.enabled:
            return

        self.capture.record_request(
            method=method,
            url=url,
            headers=headers,
            body=post_data,
            timestamp=timestamp or 0.0,
        )
        self._pending_requests[request_id] = timestamp or 0.0

    def on_response_received(
        self,
        request_id: str,
        url: str,
        status_code: int,
        headers: Optional[dict[str, str]] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        """Handle response.Received CDP event.

        Args:
            request_id: Request ID matching a prior on_request_sent.
            url: Response URL.
            status_code: HTTP status code.
            headers: Response headers.
            timestamp: Event timestamp.
        """
        if not self.capture.enabled:
            return

        # Clean up pending request tracking
        self._pending_requests.pop(request_id, None)

        self.capture.record_response(
            url=url,
            status_code=status_code,
            headers=headers,
            timestamp=timestamp or 0.0,
        )

    def on_response_body_received(
        self,
        request_id: str,
        url: str,
        body: str,
        timestamp: Optional[float] = None,
    ) -> None:
        """Handle responseBodyReceived CDP event.

        Args:
            request_id: Request ID from prior on_response_received.
            url: Response URL.
            body: Response body (may be large).
            timestamp: Event timestamp.
        """
        if not self.capture.enabled:
            return

        # Update the most recent call's response body
        # (matched by URL, in reverse order of capture time)
        for call in reversed(self.capture.calls):
            if call.request.url == url and call.response.body is None:
                call.response.body = body
                break
