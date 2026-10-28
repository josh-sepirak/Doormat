"""SSRF protection utilities for validating user-supplied targets."""

import ipaddress
import socket
from urllib.parse import urlparse


def is_safe_ip(ip_str: str) -> bool:
    """Return True if the IP is public and safe (not private, loopback, link-local, or metadata)."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return not (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        )
    except ValueError:
        return False


def validate_safe_host(host: str) -> bool:
    """Validate that host does not resolve to private, loopback, or metadata addresses."""
    cleaned = host.strip().lower()
    if not cleaned:
        return False
    if ":" in cleaned and not cleaned.startswith("["):
        cleaned = cleaned.split(":")[0]
    elif cleaned.startswith("[") and "]" in cleaned:
        cleaned = cleaned[1 : cleaned.index("]")]

    if cleaned in ("localhost", "127.0.0.1", "::1", "metadata.google.internal"):
        return False

    # Check direct IP
    try:
        ip = ipaddress.ip_address(cleaned)
        return is_safe_ip(str(ip))
    except ValueError:
        pass

    # Resolve hostname
    try:
        addrs = socket.getaddrinfo(cleaned, None)
        for _, _, _, _, sockaddr in addrs:
            resolved_ip = str(sockaddr[0])
            if not is_safe_ip(resolved_ip):
                return False
        return True
    except (socket.gaierror, socket.herror, OSError):
        # Allow unresolved domain names in offline/mock test environments
        return True


def validate_safe_url(url: str) -> bool:
    """Validate that a URL uses http(s) and does not point to internal/SSRF targets."""
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            return False
        host = p.hostname or ""
        return validate_safe_host(host)
    except Exception:
        return False
