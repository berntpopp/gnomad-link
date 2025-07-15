"""Pytest configuration and fixtures."""

import asyncio
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from gnomad_link.config import ServerConfig
from gnomad_link.logging_config import configure_logging, get_server_logger
from gnomad_link.server_manager import UnifiedServerManager


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def app():
    """Create FastAPI app instance for testing."""
    # Create test configuration
    config = ServerConfig(
        transport="http",  # Use HTTP-only for tests
        host="127.0.0.1",
        port=8000,
        mcp_path="/mcp",
        enable_docs=False,  # Disable docs for tests
        log_level="WARNING",  # Reduce logging noise
    )

    # Configure logging for tests
    configure_logging("http", "WARNING")

    # Create server manager and app
    manager = UnifiedServerManager()
    manager.logger = get_server_logger("http")
    app = await manager.create_fastapi_app(config)

    # Manually initialize the frequency service for tests
    # (normally done in lifespan, but that's not triggered in tests)
    from gnomad_link.api.client import UnifiedGnomadClient
    from gnomad_link.config import settings
    from gnomad_link.services.frequency_service import FrequencyService

    api_client = UnifiedGnomadClient()
    app.state.frequency_service = FrequencyService(
        client=api_client,
        cache_size=settings.CACHE_SIZE,
        cache_ttl_minutes=settings.CACHE_TTL_MINUTES,
    )

    return app


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
