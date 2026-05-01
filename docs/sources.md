# Rental Property Manager Sources

Doormat discovers and extracts listings from these verified property manager sources. Each entry is contributed via the [contributor workflow](./contributing/adding-a-source.md).

## Available Sources

### Pilot PM (Demonstration)
- **Entry point**: `doormat.sources.pm:pilot_pm`
- **Strategy**: `strategies/pilot-pm.json`
- **Coverage**: ~250 listings
- **Status**: ✅ Active
- **Notes**: Contributed via the specification workflow for Spec #008. Demonstrates semantic CSS selector extraction with clean HTML structure.

## Adding a New Source

See [Contributing a Rental Source](./contributing/adding-a-source.md) for the full 10-phase workflow and CLI examples.

**Quick reference**:
```bash
make add-source URL="https://example-pm.com/listings"
```

This will:
1. Validate site eligibility (robots.txt, HTTP, login walls, Captcha)
2. Collect 3-5 HTML samples via browser-harness
3. Propose CSS selectors for rental fields
4. Validate selectors against samples
5. Output strategy JSON + fixture + PR template
