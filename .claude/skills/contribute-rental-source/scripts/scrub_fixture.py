#!/usr/bin/env python3
"""Scrub PII from HTML fixtures for committed test files.

Replaces personally identifiable information with synthetic equivalents:
- Real street addresses → synthetic addresses
- Real phone numbers → test numbers
- Real emails → generic placeholder emails
- Real person names → generic placeholders or common first names
- Real photo URLs → generic paths

Usage:
    python scrub_fixture.py --input /tmp/listing.html --output tests/fixtures/html/acme-pm/sample.html
    python scrub_fixture.py --input raw.html --output scrubbed.html --verbose

WARNING: This scrubber removes common PII patterns but is NOT perfect.
Always manually review the output before committing. Look for:
- Specific addresses or location identifiers tied to real people
- Full names or unique identifiers
- Photo URLs pointing to real CDNs with user IDs
- Email addresses or phone numbers
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# Synthetic data for replacement
SYNTHETIC_ADDRESSES = [
    "123 Sycamore Lane",
    "456 Oak Avenue",
    "789 Maple Drive",
    "321 Pine Street",
    "654 Birch Road",
    "987 Cedar Court",
    "111 Elm Boulevard",
    "222 Ash Circle",
    "333 Walnut Way",
    "444 Spruce Lane",
]

SYNTHETIC_CITIES = ["Redding", "Eureka", "Fresno", "Modesto", "Merced"]
SYNTHETIC_STATES = ["CA", "NV", "OR", "AZ"]
SYNTHETIC_ZIPS = ["96001", "95501", "93650", "95350", "95341"]

SYNTHETIC_NAMES = [
    "Property Manager",
    "Leasing Agent",
    "PM Staff",
    "John",
    "Jane",
    "Alex",
    "Sam",
    "Jordan",
]

SYNTHETIC_PHONE = [
    "555-0142",
    "555-0165",
    "555-0170",
    "555-0195",
    "(555) 012-0123",  # Alt format
]

SYNTHETIC_EMAILS = [
    "contact@example.com",
    "info@example.com",
    "leasing@example.com",
    "manager@example.com",
]

COUNTER = {"address": 0, "phone": 0, "email": 0, "name": 0, "url": 0}


def scrub_address(html: str) -> str:
    """Replace real street addresses with synthetic ones."""
    # Pattern: "NNN Street/Ave/Drive/Rd/Lane" or "NNN-B Address"
    patterns = [
        r"\d+\s+[A-Z][a-z]+\s+(Street|St|Avenue|Ave|Drive|Dr|Road|Rd|Lane|Ln|Way|Blvd|Boulevard|Court|Ct|Circle|Cir|Place|Pl|Parkway|Pkwy|Terrace|Ter)",
        r"\d+\s*-\s*[A-Z]\s+[A-Z][a-z]+",  # "123-B Street"
    ]
    
    def replace_address(match):
        addr = SYNTHETIC_ADDRESSES[COUNTER["address"] % len(SYNTHETIC_ADDRESSES)]
        COUNTER["address"] += 1
        return addr
    
    for pattern in patterns:
        html = re.sub(pattern, replace_address, html)
    
    return html


def scrub_phone(html: str) -> str:
    """Replace phone numbers with test numbers."""
    patterns = [
        r"\(?(\d{3})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})",  # (123) 456-7890 or variants
        r"\+1\s?(\d{3})[\s.-]?(\d{3})[\s.-]?(\d{4})",  # +1 123 456 7890
        r"ext\.?\s*\d{2,4}",  # ext. 201, extension 1234
    ]
    
    def replace_phone(match):
        phone = SYNTHETIC_PHONE[COUNTER["phone"] % len(SYNTHETIC_PHONE)]
        COUNTER["phone"] += 1
        return phone
    
    for pattern in patterns:
        html = re.sub(pattern, replace_phone, html, flags=re.IGNORECASE)
    
    return html


def scrub_email(html: str) -> str:
    """Replace email addresses with generic placeholders."""
    # Pattern: anything@domain.xxx
    pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    
    def replace_email(match):
        email = SYNTHETIC_EMAILS[COUNTER["email"] % len(SYNTHETIC_EMAILS)]
        COUNTER["email"] += 1
        return email
    
    html = re.sub(pattern, replace_email, html)
    return html


def scrub_names(html: str) -> str:
    """Replace person names with generic placeholders."""
    # Pattern: capitalized first/last name pairs or standalone names in context
    # This is heuristic and will miss some names; manual review is essential
    patterns = [
        r"(?:Contact|Manager|Agent|Leasing):\s*([A-Z][a-z]+\s+[A-Z][a-z]+)",
        r"(?:For more info contact\s+)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        r"(?:Managed by\s+)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
    ]
    
    def replace_name(match):
        name = SYNTHETIC_NAMES[COUNTER["name"] % len(SYNTHETIC_NAMES)]
        COUNTER["name"] += 1
        return f"Contact: {name}" if "Contact" in match.group(0) else name
    
    for pattern in patterns:
        html = re.sub(pattern, replace_name, html, flags=re.IGNORECASE)
    
    return html


def scrub_photo_urls(html: str) -> str:
    """Replace real photo URLs with generic paths."""
    # Pattern: src="https://domain/photos/user-12345/image.jpg" → src="/photos/image.jpg"
    # This removes user IDs and CDN hostnames
    patterns = [
        r'src="[^"]*?(?:photos|images|cdn|media)/user-?\d+/([^"]*?)"',
        r'href="[^"]*?(?:photos|images|cdn|media)/user-?\d+/([^"]*?)"',
        r'src="https?://[^/]+(?:photos|images|cdn|media)[^"]*"',
    ]
    
    def replace_url(match):
        filename = match.group(1) if match.lastindex and match.lastindex >= 1 else "photo.jpg"
        path = f'/photos/{filename}' if filename else '/photos/photo.jpg'
        COUNTER["url"] += 1
        return f'src="{path}"' if 'src=' in match.group(0) else f'href="{path}"'
    
    for pattern in patterns:
        html = re.sub(pattern, replace_url, html)
    
    return html


def scrub_html(html: str, verbose: bool = False) -> str:
    """Run all scrubbing passes."""
    if verbose:
        print("Scrubbing PII from HTML...")
    
    original_len = len(html)
    
    # Run all scrubbing passes
    html = scrub_address(html)
    if verbose:
        print(f"  - Replaced {COUNTER['address']} addresses")
    
    html = scrub_phone(html)
    if verbose:
        print(f"  - Replaced {COUNTER['phone']} phone numbers")
    
    html = scrub_email(html)
    if verbose:
        print(f"  - Replaced {COUNTER['email']} email addresses")
    
    html = scrub_names(html)
    if verbose:
        print(f"  - Replaced {COUNTER['name']} names")
    
    html = scrub_photo_urls(html)
    if verbose:
        print(f"  - Replaced {COUNTER['url']} photo URLs")
    
    if verbose:
        print(f"\nOriginal: {original_len} bytes → Scrubbed: {len(html)} bytes")
        print("\n⚠️  IMPORTANT: Manually review the output before committing!")
        print("   Look for any remaining PII: addresses, names, emails, phone numbers.")
    
    return html


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Scrub PII from HTML fixture files"
    )
    parser.add_argument("--input", required=True, help="Input HTML file")
    parser.add_argument("--output", required=True, help="Output scrubbed HTML file")
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")
    args = parser.parse_args()
    
    try:
        input_path = Path(args.input)
        output_path = Path(args.output)
        
        if not input_path.exists():
            print(f"Error: Input file not found: {input_path}", file=sys.stderr)
            return 1
        
        # Read input
        html = input_path.read_text(encoding="utf-8")
        
        # Scrub
        scrubbed = scrub_html(html, verbose=args.verbose)
        
        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(scrubbed, encoding="utf-8")
        
        if args.verbose:
            print(f"\n✓ Saved to {output_path}")
        else:
            print(f"✓ Scrubbed {input_path} → {output_path}")
        
        print("\n⚠️  MANUAL REVIEW REQUIRED")
        print("   Before committing, inspect the output for remaining PII:")
        print(f"   - Check {output_path} for real addresses, names, emails, photos")
        print("   - Edit as needed to remove any identifying information")
        print("   - Focus on the listing details (address, contact info, descriptions)")
        
        return 0
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
