"""Pytest configuration and fixtures."""

import asyncio
from collections.abc import Generator

import pytest

from gnomad_link.logging_config import configure_logging

# Configure structlog once for the test session (console renderer, quiet level).
configure_logging("WARNING", "console")


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
