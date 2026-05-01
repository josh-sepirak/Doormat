#!/usr/bin/env python3
"""Convert browser-harness HTML samples into a doormat ExtractionStrategy.

Reads sample HTML files, proposes CSS/XPath selectors per field, verifies 
selectors match >= 3 of 5 samples, and emits a strategy JSON conforming 
to doormat's ExtractionStrategy schema.

Optionally builds an ApiRecipe from --api-* flags (requires spec #007 to be merged).

Usage:
    python from_harness.py \\
      --source-id acme-pm \\
      --display-name "Acme Property Management (Asheville, NC)" \\
      --index-url "https://acme-pm.example.com/listings" \\
      --listing-url-pattern "/listings/{listing_id}" \\
      --listing-link-selector "a.listing-card" \\
      --sample-html /tmp/listing-1.html /tmp/listing-2.html /tmp/listing-3.html /tmp/listing-4.html /tmp/listing-5.html \\
      --output strategies/acme-pm.json

Optional API recipe flags:
    --api-method GET \\
    --api-url-template "https://acme-pm.example.com/api/listings/{listing_id}" \\
    --api-headers '{"Accept": "application/json"}' \\
    --api-response-root "$.data.listing" \\
    --api-field-paths '{"address":"address","price":"rent","bedrooms":"beds"}'
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from selectolax.parser import HTMLParser


def propose_selectors_from_samples(
    sample_files: list[str], verbose: bool = False
) -> dict[str, str]:
    """Propose CSS selectors for each field by analyzing sample HTML files.
    
    For each field (address, rent, etc.), we look for common patterns:
    - Common CSS classes (price, rent, address)
    - Common data attributes
    - Common HTML structure patterns
    
    A selector is accepted if it matches >= 3 of 5 samples consistently.
    
    Returns a dict of field -> selector pairs.
    """
    if len(sample_files) < 3:
        raise ValueError(f"Need at least 3 samples, got {len(sample_files)}")
    
    samples: list[HTMLParser] = []
    for sample_file in sample_files:
        path = Path(sample_file)
        if not path.exists():
            raise FileNotFoundError(f"Sample file not found: {sample_file}")
        
        html_content = path.read_text(encoding="utf-8")
        samples.append(HTMLParser(html_content))
    
    if verbose:
        print(f"Loaded {len(samples)} sample HTML files")
        print("Analyzing for common selectors...\n")
    
    # Try to find selectors for each field
    proposed_selectors: dict[str, str] = {}
    
    # For each target field, propose a selector and validate it matches >= 3 samples
    field_patterns = {
        "address": [
            "h1.address",
            "h1.title",
            "h1.property-title",
            "[data-test*='address']",
            ".address",
            ".location",
            ".property-address",
        ],
        "rent": [
            ".price",
            ".monthly-rent",
            ".rent",
            "[data-test*='price']",
            ".monthly-price",
            "span.rent",
        ],
        "bedrooms": [
            ".beds",
            ".bedrooms",
            ".bed-count",
            "[data-test*='bed']",
            "span.beds",
        ],
        "bathrooms": [
            ".baths",
            ".bathrooms",
            ".bath-count",
            "[data-test*='bath']",
            "span.baths",
        ],
        "sqft": [
            ".sqft",
            ".square-feet",
            ".sf",
            "[data-test*='sqft']",
            ".size",
        ],
        "pets_policy": [
            ".pets",
            ".pet-policy",
            "[data-test*='pet']",
            "p.pet-policy",
        ],
        "amenities": [
            ".amenities",
            "ul.amenities",
            ".amenities-list",
            "[data-test*='amenities']",
        ],
        "photos": [
            "img.gallery-image",
            "img[alt*='photo']",
            ".gallery img",
            ".photos img",
        ],
        "description": [
            ".description",
            ".listing-description",
            "div.description",
            "[data-test*='description']",
        ],
    }
    
    for field, patterns in field_patterns.items():
        best_selector = None
        best_match_count = 0
        
        for selector in patterns:
            matches = 0
            for sample in samples:
                try:
                    elements = sample.select(selector)
                    if elements:
                        matches += 1
                except Exception:
                    pass
            
            if matches >= 3 and matches > best_match_count:
                best_selector = selector
                best_match_count = matches
        
        if best_selector:
            proposed_selectors[field] = best_selector
            if verbose:
                print(f"✓ {field}: {best_selector} (matched {best_match_count}/{len(samples)} samples)")
        else:
            if verbose:
                print(f"✗ {field}: no selector matched >= 3 samples (manual entry required)")
    
    return proposed_selectors


def build_strategy_json(
    source_id: str,
    display_name: str,
    field_selectors: dict[str, str],
    api_recipe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the strategy JSON object."""
    # Ensure required fields are present
    required_fields = {"address", "rent", "bedrooms", "bathrooms"}
    provided = set(field_selectors.keys())
    
    if not required_fields.issubset(provided):
        missing = required_fields - provided
        print(f"Warning: Missing required field selectors: {missing}", file=sys.stderr)
    
    strategy: dict[str, Any] = {
        "field_selectors": field_selectors,
        "pre_extraction_actions": [],
        "notes": f"Generated by contribute-rental-source skill for {display_name}",
        "api_recipe": api_recipe,
    }
    
    return strategy


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Convert browser-harness samples to doormat ExtractionStrategy"
    )
    
    # Required args
    parser.add_argument("--source-id", required=True, help="Source ID (e.g., acme-pm)")
    parser.add_argument("--display-name", required=True, help="Display name for docs")
    parser.add_argument("--index-url", required=True, help="Listing index URL")
    parser.add_argument(
        "--listing-url-pattern",
        required=True,
        help="URL pattern (e.g., /listings/{listing_id})",
    )
    parser.add_argument(
        "--listing-link-selector",
        required=True,
        help="CSS selector for listing links on index",
    )
    parser.add_argument(
        "--sample-html", nargs="+", required=True, help="List of sample HTML files"
    )
    parser.add_argument("--output", required=True, help="Output strategy JSON file")
    
    # Optional manual overrides
    parser.add_argument(
        "--address-selector", help="Override proposed address selector"
    )
    parser.add_argument("--rent-selector", help="Override proposed rent selector")
    parser.add_argument(
        "--bedrooms-selector", help="Override proposed bedrooms selector"
    )
    parser.add_argument(
        "--bathrooms-selector", help="Override proposed bathrooms selector"
    )
    parser.add_argument("--sqft-selector", help="Override proposed sqft selector")
    parser.add_argument(
        "--pets-policy-selector", help="Override proposed pets_policy selector"
    )
    parser.add_argument(
        "--amenities-selector", help="Override proposed amenities selector"
    )
    parser.add_argument("--photos-selector", help="Override proposed photos selector")
    parser.add_argument(
        "--description-selector", help="Override proposed description selector"
    )
    
    # Optional API recipe (requires spec #007)
    parser.add_argument(
        "--api-method",
        choices=["GET", "POST"],
        help="API HTTP method (if JSON endpoint available)",
    )
    parser.add_argument(
        "--api-url-template", help="API URL template (e.g., /api/listings/{listing_id})"
    )
    parser.add_argument(
        "--api-headers",
        help="API headers as JSON (e.g., '{\"Accept\": \"application/json\"}')",
    )
    parser.add_argument(
        "--api-response-root", default="$", help="JSONPath to listing in response"
    )
    parser.add_argument(
        "--api-field-paths",
        help="Field JSONPaths as JSON (e.g., '{\"address\": \"$.address\"}')",
    )
    parser.add_argument(
        "--api-listing-id", help="Listing ID used during API capture (for validation)"
    )
    
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Validate inputs
    if len(args.sample_html) < 3:
        print("Error: Need at least 3 sample HTML files", file=sys.stderr)
        return 1
    
    if len(args.sample_html) > 5:
        print(
            f"Warning: Provided {len(args.sample_html)} samples (expected <= 5); using first 5",
            file=sys.stderr,
        )
        args.sample_html = args.sample_html[:5]
    
    try:
        # Propose selectors from samples
        proposed_selectors = propose_selectors_from_samples(args.sample_html, args.verbose)
        
        # Apply manual overrides
        overrides = {
            "address": args.address_selector,
            "rent": args.rent_selector,
            "bedrooms": args.bedrooms_selector,
            "bathrooms": args.bathrooms_selector,
            "sqft": args.sqft_selector,
            "pets_policy": args.pets_policy_selector,
            "amenities": args.amenities_selector,
            "photos": args.photos_selector,
            "description": args.description_selector,
        }
        
        for field, override in overrides.items():
            if override:
                proposed_selectors[field] = override
                if args.verbose:
                    print(f"Overriding {field}: {override}")
        
        # Build API recipe if provided
        api_recipe = None
        if args.api_method and args.api_url_template:
            # Parse API headers if provided
            api_headers: dict[str, str] = {}
            if args.api_headers:
                try:
                    api_headers = json.loads(args.api_headers)
                except json.JSONDecodeError as e:
                    print(f"Error parsing API headers: {e}", file=sys.stderr)
                    return 1
            
            # Parse API field paths if provided
            api_field_paths: dict[str, str] = {}
            if args.api_field_paths:
                try:
                    api_field_paths = json.loads(args.api_field_paths)
                except json.JSONDecodeError as e:
                    print(f"Error parsing API field paths: {e}", file=sys.stderr)
                    return 1
            
            # Build API recipe
            api_recipe = {
                "method": args.api_method,
                "url_template": args.api_url_template,
                "headers": api_headers,
                "body_template": None,
                "response_root": args.api_response_root,
                "field_paths": api_field_paths,
                "extractable_fields": list(api_field_paths.keys()),
                "captured_at": datetime.now(UTC).isoformat(),
                "captured_from_listing_id": args.api_listing_id or "sample",
                "last_validated_at": None,
                "last_failure_at": None,
                "failure_count": 0,
                "confidence": "medium",  # Marked as medium pending validation
                "capture_notes": "Generated from contributor input during skill workflow",
            }
            
            if args.verbose:
                print(f"Built API recipe with {len(api_field_paths)} field paths")
        
        # Build strategy JSON
        strategy = build_strategy_json(
            args.source_id,
            args.display_name,
            proposed_selectors,
            api_recipe=api_recipe,
        )
        
        # Write output
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(strategy, f, indent=2)
        
        print(f"✓ Generated strategy: {output_path}")
        print(f"\nStrategy summary:")
        print(f"  - Source ID: {args.source_id}")
        print(f"  - Display name: {args.display_name}")
        print(f"  - Field selectors: {len(proposed_selectors)}")
        for field, selector in sorted(proposed_selectors.items()):
            marker = "✓" if field in {"address", "rent", "bedrooms", "bathrooms"} else " "
            print(f"    {marker} {field}: {selector}")
        
        if api_recipe:
            print(f"  - API recipe: yes ({len(api_field_paths)} fields)")
        else:
            print(f"  - API recipe: no")
        
        print(f"\nNext step: Run validation script")
        print(
            f"  python scripts/validate_strategy.py --strategy {output_path} --fixture tests/fixtures/html/{args.source_id}/sample.html"
        )
        
        return 0
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
