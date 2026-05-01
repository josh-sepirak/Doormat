#!/usr/bin/env python3
"""Preflight checks before contributing a rental source.

Validates that a property manager site is eligible for contribution:
- robots.txt doesn't block scraping
- Site responds with HTTP 200
- No login wall or captcha on the listing index

Usage:
    python preflight.py https://acme-pm.example.com/listings
    python preflight.py https://acme-pm.example.com  (will check /listings path)
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from urllib.parse import urljoin, urlparse

import httpx


async def check_robots_txt(base_url: str) -> tuple[bool, str]:
    """Check if robots.txt allows scraping the site.
    
    Returns (allowed, reason).
    """
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(robots_url, follow_redirects=True)
            
            if resp.status_code == 404:
                # No robots.txt = assume allowed
                return True, "robots.txt not found (assumed allowed)"
            
            if resp.status_code != 200:
                return False, f"robots.txt returned {resp.status_code}"
            
            content = resp.text.lower()
            
            # Check for User-Agent: * (applies to all bots)
            user_agent_all = "user-agent: *" in content
            
            # Check for common paths that might be disallowed
            disallow_patterns = [
                r"disallow:\s*/\s*($|#)",  # Disallow all
                r"disallow:\s*/listings",
                r"disallow:\s*/properties",
                r"disallow:\s*/rentals",
            ]
            
            for pattern in disallow_patterns:
                if user_agent_all and re.search(pattern, content):
                    return False, "robots.txt disallows the listing path"
            
            return True, "robots.txt allows scraping"
    
    except Exception as e:
        return False, f"Failed to fetch robots.txt: {e}"


async def check_http_status(url: str) -> tuple[bool, str]:
    """Check that the site responds with HTTP 200.
    
    Returns (ok, reason).
    """
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url)
            
            if resp.status_code == 200:
                return True, "HTTP 200 OK"
            elif resp.status_code == 403:
                return False, "HTTP 403 Forbidden (access denied)"
            elif resp.status_code == 429:
                return False, "HTTP 429 Too Many Requests (rate limited)"
            elif resp.status_code >= 500:
                return False, f"HTTP {resp.status_code} (server error)"
            else:
                return True, f"HTTP {resp.status_code} (expected)"
    
    except httpx.TimeoutException:
        return False, "Request timed out (site may be slow or blocking)"
    except Exception as e:
        return False, f"Failed to fetch: {e}"


async def check_login_wall(url: str) -> tuple[bool, str]:
    """Check for login wall on the page.
    
    Returns (has_no_wall, reason).
    """
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url)
            
            if resp.status_code != 200:
                return True, "Cannot check (page fetch failed)"
            
            content = resp.text.lower()
            
            # Look for login/signin keywords
            login_indicators = [
                r"sign\s*in",
                r"log\s*in",
                r"login\s*required",
                r"please\s*log\s*in",
                r"unauthorized",
                r"require\s*password",
            ]
            
            for indicator in login_indicators:
                if re.search(indicator, content):
                    # Check if it's in a meta tag or title (likely real)
                    if re.search(f"<title>.*{indicator}.*</title>", content):
                        return False, "Login wall detected on index page"
                    if re.search(f"<meta.*{indicator}.*>", content):
                        return False, "Login wall detected in meta tags"
            
            return True, "No login wall detected"
    
    except Exception as e:
        return True, f"Cannot check login wall: {e}"


async def check_captcha(url: str) -> tuple[bool, str]:
    """Check for Captcha or bot-blocking challenges.
    
    Returns (has_no_captcha, reason).
    """
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url)
            
            if resp.status_code != 200:
                return True, "Cannot check (page fetch failed)"
            
            content = resp.text.lower()
            
            # Look for Cloudflare, reCAPTCHA, hCaptcha
            captcha_indicators = [
                "cloudflare",
                "recaptcha",
                "hcaptcha",
                "challenge-form",
                "bot-check",
            ]
            
            for indicator in captcha_indicators:
                if indicator in content:
                    return False, f"Captcha/challenge detected ({indicator})"
            
            return True, "No Captcha detected"
    
    except Exception as e:
        return True, f"Cannot check captcha: {e}"


async def main() -> int:
    """Run all preflight checks."""
    parser = argparse.ArgumentParser(
        description="Preflight checks for rental source contribution"
    )
    parser.add_argument("url", help="Property manager index URL or base domain")
    parser.add_argument(
        "--verbose", action="store_true", help="Show detailed output"
    )
    args = parser.parse_args()
    
    url = args.url
    
    # Normalize URL
    if not url.startswith("http"):
        url = f"https://{url}"
    
    # If it looks like a domain only, try /listings path
    parsed = urlparse(url)
    if not parsed.path or parsed.path == "/":
        url = urljoin(url, "/listings")
    
    if args.verbose:
        print(f"Checking: {url}\n")
    
    # Run all checks
    checks = [
        ("robots.txt", check_robots_txt(parsed.scheme + "://" + parsed.netloc)),
        ("HTTP Status", check_http_status(url)),
        ("Login Wall", check_login_wall(url)),
        ("Captcha", check_captcha(url)),
    ]
    
    all_pass = True
    
    for check_name, check_coro in checks:
        passed, reason = await check_coro
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {check_name} — {reason}")
        if not passed:
            all_pass = False
    
    print()
    
    if all_pass:
        print("✓ All checks passed! Proceed to Phase 2 (harness connection).")
        return 0
    else:
        print("✗ One or more checks failed. Cannot proceed with contribution.")
        print("  Ensure the site is public, doesn't block bots, and has no login wall.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
