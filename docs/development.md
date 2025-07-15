# Development Guide

## Development Environment Setup

### Prerequisites
- Python 3.9+
- Git
- Make (optional, for convenience commands)

### Installation
```bash
# Clone repository
git clone <repository-url>
cd gnomad-link

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Or use the install script
./install.sh
```

### Development Dependencies
```bash
# Install development tools
pip install -e ".[dev]"

# Includes:
# - pytest (testing)
# - pytest-asyncio (async testing)
# - pytest-cov (coverage)
# - black (code formatting)
# - isort (import sorting)
# - ruff (linting)
# - flake8 (additional linting)
# - mypy (type checking)
# - httpx (HTTP client for tests)
# - respx (HTTP mocking)
```

## Development Workflow

### Code Style and Linting

We use multiple tools to maintain code quality:

#### Formatting
```bash
# Format code (black + isort)
make format

# Or manually
black .
isort .
```

#### Linting
```bash
# Run all linters
make lint

# Individual linters
ruff check .          # Fast Python linter
flake8 .             # Additional style checks
mypy .               # Type checking
```

#### Code Quality Standards
- **Line Length**: 120 characters maximum
- **Type Hints**: Required for all public functions
- **Docstrings**: Required for all public classes and functions
- **Import Sorting**: Alphabetical with isort
- **Formatting**: Black with default settings

### Testing

#### Running Tests
```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test file
pytest tests/test_variant_endpoints.py

# Run specific test
pytest tests/test_variant_endpoints.py::TestVariantEndpoints::test_brca2_deletion_variant

# Run with verbose output
pytest -v

# Run with live logging
pytest -s
```

#### Test Structure
```
tests/
├── conftest.py                    # Test configuration and fixtures
├── test_base_client.py           # Base client tests
├── test_clinvar_endpoints.py     # ClinVar API tests
├── test_gene_endpoints.py        # Gene API tests
├── test_liftover_endpoints.py    # Liftover API tests
├── test_variant_endpoints.py     # Variant API tests
└── ...
```

#### Writing Tests
```python
import pytest
from httpx import AsyncClient

class TestVariantEndpoints:
    """Test variant API endpoints."""

    @pytest.mark.asyncio
    async def test_variant_frequency(self, client: AsyncClient):
        """Test variant frequency endpoint."""
        response = await client.get("/api/variants/1-55039447-G-T?dataset=gnomad_r4")
        
        assert response.status_code == 200
        data = response.json()
        assert "variant_id" in data
        assert "frequencies" in data
```

#### Test Patterns
- **Async Tests**: Use `@pytest.mark.asyncio` for async functions
- **Fixtures**: Use `client` fixture for HTTP testing
- **Mocking**: Use `respx` for external API mocking
- **Assertions**: Test both success and error conditions
- **Data Validation**: Verify response structure and types

#### Coverage Requirements
- **Minimum**: 90% overall coverage
- **New Code**: 100% coverage required
- **Critical Paths**: Error handling must be tested

### Development Commands

#### Make Commands
```bash
# Setup and installation
make install-dev        # Install development dependencies
make clean              # Remove cache and build files

# Code quality
make format             # Format code with black and isort
make lint               # Run all linters
make test               # Run all tests
make test-cov           # Run tests with coverage report

# Server management
make run-dev            # Run in development mode
make run-prod           # Run in production mode
```

#### Manual Commands
```bash
# Development server with auto-reload
python server.py --transport unified --dev

# STDIO server for AI assistant testing
python server.py --transport stdio

# HTTP-only server
python server.py --transport http
```

## Architecture and Code Organization

### Project Structure
```
gnomad_link/
├── __init__.py
├── api/                    # API layer
│   ├── __init__.py
│   ├── base_client.py     # Base GraphQL client
│   ├── client.py          # Unified gnomAD client
│   └── routes/            # FastAPI route handlers
│       ├── __init__.py
│       ├── variant.py     # Variant endpoints
│       ├── gene.py        # Gene endpoints
│       └── ...
├── cli.py                 # Command-line interface
├── config.py              # Configuration management
├── exceptions.py          # Custom exceptions
├── graphql/               # GraphQL layer
│   ├── __init__.py
│   ├── queries/           # GraphQL queries
│   │   ├── common/        # Shared queries
│   │   ├── v2/           # v2-specific queries
│   │   ├── v3/           # v3-specific queries
│   │   └── v4/           # v4-specific queries
│   ├── query_builder.py  # Query construction
│   └── query_loader.py   # Query loading and caching
├── logging_config.py      # Logging configuration
├── models/                # Pydantic models
│   ├── __init__.py
│   ├── variant_models.py  # Variant data models
│   ├── gene_models.py     # Gene data models
│   └── ...
├── server_manager.py      # Unified server management
├── services/              # Business logic
│   ├── __init__.py
│   └── frequency_service.py
└── transports/            # Transport abstraction
    ├── __init__.py
    ├── base.py           # Base transport class
    └── factory.py        # Transport factory
```

### Design Patterns

#### Dependency Injection
```python
# services/frequency_service.py
class FrequencyService:
    def __init__(self, client: UnifiedGnomadClient, cache_size: int = 1024):
        self.client = client
        self.cache = LRUCache(cache_size)

# routes/dependencies.py
def get_service() -> FrequencyService:
    return request.app.state.frequency_service
```

#### Factory Pattern
```python
# transports/factory.py
class TransportFactory:
    @staticmethod
    def create_transport(transport_type: str) -> BaseTransport:
        if transport_type == "stdio":
            return StdioTransport()
        elif transport_type == "http":
            return HttpTransport()
        else:
            raise ValueError(f"Unknown transport: {transport_type}")
```

#### Configuration Management
```python
# config.py
class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    GNOMAD_API_URL: str = "https://gnomad.broadinstitute.org/api"
    CACHE_SIZE: int = 1024
    
    model_config = {"env_file": ".env"}

# Usage
settings = Settings()
```

### Adding New Features

#### Adding a New API Endpoint

1. **Create Pydantic Models**:
```python
# models/new_feature_models.py
from pydantic import BaseModel
from typing import List, Optional

class NewFeatureRequest(BaseModel):
    query: str
    filters: Optional[List[str]] = None

class NewFeatureResponse(BaseModel):
    results: List[dict]
    total: int
```

2. **Add GraphQL Query**:
```graphql
# graphql/queries/common/new_feature.graphql
query newFeature($query: String!, $filters: [String!]) {
    newFeature(query: $query, filters: $filters) {
        results {
            id
            name
            description
        }
        total
    }
}
```

3. **Extend Client**:
```python
# api/client.py
class UnifiedGnomadClient:
    async def get_new_feature(self, query: str, filters: Optional[List[str]] = None) -> dict:
        variables = {"query": query}
        if filters:
            variables["filters"] = filters
        
        return await self.execute_query("new_feature", variables)
```

4. **Add API Route**:
```python
# api/routes/new_feature.py
from fastapi import APIRouter, Depends, Query
from ..dependencies import get_service

router = APIRouter(prefix="/new-feature", tags=["New Feature"])

@router.get("/", response_model=NewFeatureResponse)
async def get_new_feature(
    query: str = Query(..., description="Search query"),
    filters: Optional[List[str]] = Query(None, description="Filter options"),
    service: FrequencyService = Depends(get_service),
) -> NewFeatureResponse:
    result = await service.client.get_new_feature(query, filters)
    return NewFeatureResponse(**result)
```

5. **Add MCP Tool**:
```python
# server_manager.py
@app.tool()
async def get_new_feature(
    query: str = Field(..., description="Search query"),
    filters: Optional[List[str]] = Field(None, description="Filter options"),
) -> dict:
    """Get new feature data from gnomAD."""
    result = await frequency_service.client.get_new_feature(query, filters)
    return result
```

6. **Add Tests**:
```python
# tests/test_new_feature_endpoints.py
class TestNewFeatureEndpoints:
    @pytest.mark.asyncio
    async def test_new_feature_search(self, client: AsyncClient):
        params = {"query": "test"}
        response = await client.get("/api/new-feature/", params=params)
        
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total" in data
```

## Debugging and Troubleshooting

### Debug Mode
```bash
# Start server with debug logging
python server.py --transport unified --log-level DEBUG

# Development mode with auto-reload
python server.py --transport unified --dev
```

### Common Issues

#### Import Errors
```bash
# Ensure package is installed in development mode
pip install -e .

# Check Python path
python -c "import gnomad_link; print(gnomad_link.__file__)"
```

#### Port Already in Use
```bash
# Find process using port
lsof -i :8000

# Kill process
kill -9 <PID>

# Use different port
python server.py --port 8001
```

#### Cache Issues
```bash
# Clear cache via API
curl -X POST http://localhost:8000/api/cache/clear

# Or restart server
```

#### Test Failures
```bash
# Run specific failing test
pytest tests/test_file.py::test_function -v

# Run with pdb debugger
pytest tests/test_file.py::test_function --pdb

# Check test coverage
pytest --cov=gnomad_link tests/
```

### Performance Profiling
```python
# Add timing to functions
import time
from functools import wraps

def timing_decorator(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        end = time.time()
        print(f"{func.__name__} took {end - start:.2f}s")
        return result
    return wrapper

# Use in development
@timing_decorator
async def slow_function():
    # ... function code
```

### Memory Usage
```python
# Monitor memory usage
import psutil
import os

def get_memory_usage():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024  # MB

# Use in monitoring
print(f"Memory usage: {get_memory_usage():.2f} MB")
```

## Contributing Guidelines

### Code Review Process
1. **Create Feature Branch**: `git checkout -b feature/new-feature`
2. **Implement Changes**: Follow code style and testing requirements
3. **Run Tests**: Ensure all tests pass
4. **Submit PR**: Include description and test results
5. **Code Review**: Address reviewer feedback
6. **Merge**: Squash merge to main branch

### Commit Messages
```bash
# Format: type(scope): description
feat(api): add new variant search endpoint
fix(cache): resolve memory leak in LRU cache
docs(readme): update installation instructions
test(liftover): add comprehensive liftover tests
```

### Documentation
- **API Changes**: Update OpenAPI documentation
- **Architecture Changes**: Update architecture.md
- **New Features**: Add usage examples
- **Breaking Changes**: Update migration guide

### Release Process
1. **Version Bump**: Update version in pyproject.toml
2. **Changelog**: Update CHANGELOG.md
3. **Testing**: Run full test suite
4. **Documentation**: Update docs
5. **Tag Release**: Create git tag
6. **Deploy**: Deploy to production

This development guide provides the foundation for contributing to and maintaining the gnomAD-link project effectively.