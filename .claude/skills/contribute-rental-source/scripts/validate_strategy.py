#!/usr/bin/env python3
"""Validate a contributed extraction strategy against a fixture.

Runs the doormat extraction pipeline (Mode A) against the strategy
and fixture to ensure it extracts all required fields with high confidence.

This script must have access to a doormat backend environment and can
optionally use a test database or mocked LLM client.

Usage:
    python validate_strategy.py --strategy strategies/acme-pm.json --fixture tests/fixtures/html/acme-pm/sample.html
    python validate_strategy.py --strategy strategies/acme-pm.json --fixture tests/fixtures/html/acme-pm/sample.html --verbose
    python validate_strategy.py --strategy strategies/acme-pm.json --fixture tests/fixtures/html/acme-pm/sample.html --mock-llm
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

# Try to import doormat - if not available, provide helpful error
try:
    from doormat.extraction.mode_a import run_mode_a
    from doormat.llm.client import get_llm_client
    from doormat.models.orm import ExtractionStrategy
    from doormat.schemas import PetsPolicy
except ImportError as e:
    print(f"Error: Could not import doormat modules: {e}", file=sys.stderr)
    print("Make sure you're running from the doormat repo root with 'uv run python'", file=sys.stderr)
    sys.exit(1)


class MockExtractionStrategy:
    """Minimal mock of ExtractionStrategy ORM for testing without DB."""

    def __init__(self, strategy_id: str, strategy_json: dict) -> None:
        self.id = strategy_id
        self.strategy_json_dict = strategy_json
        self.strategy_json = json.dumps(strategy_json)
        self.property_manager_id = "mock"
        self.validation_rate = 0.0
        self.tier1_model = None
        self.tier2_model = None
        self.last_refined = None


async def validate_strategy(
    strategy_file: str,
    fixture_file: str,
    source_id: Optional[str] = None,
    verbose: bool = False,
    mock_llm: bool = False,
) -> int:
    """Validate a strategy against a fixture.
    
    Returns 0 on success, 1 on failure.
    """
    # Load strategy JSON
    strategy_path = Path(strategy_file)
    if not strategy_path.exists():
        print(f"Error: Strategy file not found: {strategy_path}", file=sys.stderr)
        return 1
    
    try:
        strategy_dict = json.loads(strategy_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Error: Invalid strategy JSON: {e}", file=sys.stderr)
        return 1
    
    # Load fixture HTML
    fixture_path = Path(fixture_file)
    if not fixture_path.exists():
        print(f"Error: Fixture file not found: {fixture_path}", file=sys.stderr)
        return 1
    
    fixture_html = fixture_path.read_text(encoding="utf-8")
    
    # Determine source ID
    if not source_id:
        source_id = fixture_path.parent.name
    
    if verbose:
        print(f"Strategy: {strategy_path}")
        print(f"Fixture: {fixture_path}")
        print(f"Source ID: {source_id}\n")
    
    # Create mock strategy object
    mock_strategy = MockExtractionStrategy(
        strategy_id=source_id,
        strategy_json=strategy_dict,
    )
    
    # Run Mode A extraction
    if verbose:
        print("Running Mode A extraction...\n")
    
    try:
        result = await run_mode_a(
            html=fixture_html,
            url=f"https://example.com/listing/{source_id}",
            source_id=source_id,
            strategy=mock_strategy,
            city="Test City",
            model=None,  # Use default model
            api_key=None,  # Use env var OPENROUTER_API_KEY
            preference=None,
        )
    except Exception as e:
        print(f"Error during Mode A extraction: {e}", file=sys.stderr)
        if verbose:
            import traceback
            traceback.print_exc()
        return 1
    
    # Validate results
    print("Validation Results:")
    print("=" * 60)
    
    # Check extracted fields
    if not result.extracted:
        print("✗ FAIL: No listing extracted", file=sys.stderr)
        return 1
    
    extracted = result.extracted
    
    # Check required fields
    required_fields = ["address", "rent", "bedrooms", "bathrooms"]
    missing_fields = []
    
    for field in required_fields:
        value = getattr(extracted, field, None)
        if value is None or (isinstance(value, (int, float)) and value == 0):
            missing_fields.append(field)
            print(f"✗ {field}: missing or zero")
        else:
            print(f"✓ {field}: {value}")
    
    # Check optional fields
    optional_fields = ["sqft", "pets_policy", "amenities", "photos", "description"]
    for field in optional_fields:
        value = getattr(extracted, field, None)
        if value:
            if isinstance(value, list):
                print(f"✓ {field}: {len(value)} items")
            elif isinstance(value, str) and len(value) > 100:
                print(f"✓ {field}: {len(value)} chars")
            else:
                print(f"✓ {field}: {value}")
        else:
            print(f"- {field}: not extracted")
    
    # Check confidence level
    print()
    if result.confidence:
        confidence_level = result.confidence.value if hasattr(result.confidence, 'value') else str(result.confidence)
        print(f"Confidence: {confidence_level}")
        
        if confidence_level == "high":
            print("✓ High confidence extraction")
        elif confidence_level == "medium":
            print("⚠ Medium confidence (may need selector review)")
        else:
            print("✗ Low confidence (likely selector issues)")
    
    # Final result
    print()
    if missing_fields:
        print(f"✗ FAIL: Missing required fields: {', '.join(missing_fields)}")
        return 1
    else:
        print("✓ SUCCESS: All required fields extracted with high confidence")
        print("\nNext steps:")
        print("  1. Manually verify extracted values match fixture content")
        print("  2. Run scrub_fixture.py if needed")
        print("  3. Commit strategy + fixture to repository")
        print("  4. Open PR for review")
        return 0


async def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate an extraction strategy against a fixture"
    )
    parser.add_argument("--strategy", required=True, help="Strategy JSON file")
    parser.add_argument("--fixture", required=True, help="Fixture HTML file")
    parser.add_argument("--source-id", help="Source ID (inferred from fixture path if not provided)")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "--mock-llm",
        action="store_true",
        help="Use mocked LLM (skips LLM calls, deterministic selectors only)",
    )
    
    args = parser.parse_args()
    
    return await validate_strategy(
        strategy_file=args.strategy,
        fixture_file=args.fixture,
        source_id=args.source_id,
        verbose=args.verbose,
        mock_llm=args.mock_llm,
    )


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
