.PHONY: help install install-dev format lint test test-cov clean run-dev run-prod

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install production dependencies
	pip install -e .

install-dev:  ## Install development dependencies
	pip install -e ".[dev]"

format:  ## Format code with black and isort
	black .
	isort .

lint:  ## Run all linters
	ruff check .
	flake8 .
	mypy gnomad_link

test:  ## Run tests
	pytest

test-cov:  ## Run tests with coverage
	pytest --cov=gnomad_link --cov-report=html --cov-report=term

clean:  ## Clean up cache and build files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov .mypy_cache .ruff_cache
	rm -rf build dist *.egg-info

run-dev:  ## Run the unified server in development mode
	python server.py

run-prod:  ## Run the unified server in production mode
	uvicorn server:app --host 0.0.0.0 --port 8000 --workers 4

run-mcp:  ## Run MCP server in STDIO mode for AI assistants
	python mcp_server.py