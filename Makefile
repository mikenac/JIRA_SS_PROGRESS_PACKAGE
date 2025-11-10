.PHONY: help install test test-verbose test-coverage run dry-run lint lint-fix clean clean-all

# Default target - show help
help:
	@echo "Available commands:"
	@echo "  make install        - Install package and dependencies"
	@echo "  make install-dev    - Install package with dev dependencies"
	@echo "  make test           - Run all tests (auto-installs dev deps)"
	@echo "  make test-verbose   - Run tests with verbose output (auto-installs dev deps)"
	@echo "  make test-coverage  - Run tests with coverage report (auto-installs dev deps)"
	@echo "  make run            - Run the sync (requires .env)"
	@echo "  make dry-run        - Run the sync in dry-run mode"
	@echo "  make lint           - Run linter (auto-installs dev deps)"
	@echo "  make lint-fix       - Run linter and auto-fix issues (auto-installs dev deps)"
	@echo "  make clean          - Clean temporary files and caches"
	@echo "  make clean-all      - Clean everything including venv"

# Install package and dependencies
install:
	uv pip install -e .

# Install package with development dependencies
install-dev:
	uv pip install -e ".[dev]"

# Run all tests (ensures dev dependencies are installed)
test: install-dev
	pytest

# Run tests with verbose output (ensures dev dependencies are installed)
test-verbose: install-dev
	pytest -v

# Run tests with coverage report (ensures dev dependencies are installed)
test-coverage: install-dev
	pytest --cov=jira_ss_progress --cov-report=term-missing --cov-report=html
	@echo ""
	@echo "Coverage report generated in htmlcov/index.html"

# Run the sync (production mode - will make actual changes)
run:
	@echo "Running sync in PRODUCTION mode (will make changes)..."
	@echo "Press Ctrl+C within 3 seconds to cancel..."
	@sleep 3
	uv run jira-ss-sync --log-level INFO

# Run the sync in dry-run mode (preview only)
dry-run:
	@echo "Running sync in DRY-RUN mode (preview only)..."
	DRY_RUN=1 uv run jira-ss-sync --log-level INFO

# Run linter (ensures dev dependencies are installed)
lint: install-dev
	ruff check jira_ss_progress/

# Run linter and auto-fix issues (ensures dev dependencies are installed)
lint-fix: install-dev
	ruff check --fix jira_ss_progress/

# Clean temporary files and caches
clean:
	@echo "Cleaning temporary files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	rm -f .coverage
	rm -rf build
	rm -rf dist
	@echo "Clean complete!"

# Clean everything including virtual environment
clean-all: clean
	@echo "Removing virtual environment..."
	rm -rf .venv
	@echo "All clean!"
