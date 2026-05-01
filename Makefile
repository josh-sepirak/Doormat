# doormat Makefile - development and contribution utilities

.PHONY: help install dev lint test add-source

help:
	@echo "doormat development targets:"
	@echo "  make install      Install dependencies (uv sync --dev)"
	@echo "  make dev          Start dev server"
	@echo "  make lint         Run ruff linter"
	@echo "  make test         Run test suite"
	@echo "  make add-source   Interactive contributor workflow for adding a rental source"

install:
	uv sync --dev

dev:
	uv run uvicorn doormat.main:app --reload --host 0.0.0.0 --port 8000

lint:
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

test:
	uv run pytest -xvs

# Contributor workflow for adding a new rental source
# Usage: make add-source URL=https://acme-pm.example.com/listings
add-source:
	@if [ -z "$(URL)" ]; then \
		echo "Usage: make add-source URL=https://property-manager.example.com/listings"; \
		echo ""; \
		echo "This target guides you through adding a new rental source via the contributor skill."; \
		echo "See docs/contributing/adding-a-source.md for details."; \
		exit 1; \
	fi
	@echo "Starting contributor workflow for: $(URL)"
	@echo ""
	@echo "Phase 1: Preflight checks..."
	uv run python .claude/skills/contribute-rental-source/scripts/preflight.py $(URL) --verbose
	@echo ""
	@echo "✓ Preflight passed!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Run phases 2-4 using the browser-harness skill"
	@echo "  2. Capture 5 sample HTML files"
	@echo "  3. Run: uv run python .claude/skills/contribute-rental-source/scripts/from_harness.py --help"
	@echo "  4. See docs/contributing/adding-a-source.md for complete workflow"
