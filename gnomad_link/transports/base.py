"""Base transport interface for gnomAD unified server."""

from abc import ABC, abstractmethod
from typing import Any, Optional

from fastapi import FastAPI
from fastmcp import FastMCP

from ..config import ServerConfig
from ..exceptions import TransportError


class BaseTransport(ABC):
    """Base class for transport implementations."""

    def __init__(self, config: ServerConfig):
        """Initialize base transport with configuration."""
        self.config = config
        self.app: Optional[FastAPI] = None
        self.mcp: Optional[FastMCP] = None
        self.logger = None

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the transport."""
        pass

    @abstractmethod
    async def start(self) -> None:
        """Start the transport."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the transport."""
        pass

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        """Get transport status."""
        pass

    @abstractmethod
    def get_transport_name(self) -> str:
        """Get transport name."""
        pass

    def validate_config(self) -> None:
        """Validate transport configuration."""
        if not self.config:
            raise TransportError("Configuration is required", self.get_transport_name())

    async def health_check(self) -> dict[str, Any]:
        """Perform health check."""
        return {
            "status": "healthy",
            "transport": self.get_transport_name(),
            "config": {
                "host": self.config.host,
                "port": self.config.port,
                "log_level": self.config.log_level,
            },
        }
