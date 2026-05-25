"""Transport factory for creating transport instances."""

from __future__ import annotations

from ..config import ServerConfig
from ..exceptions import ConfigurationError
from .base import BaseTransport


class TransportFactory:
    """Factory for creating transport-specific configurations."""

    _transports: dict[str, type[BaseTransport]] = {}

    @classmethod
    def register_transport(cls, name: str, transport_class: type[BaseTransport]) -> None:
        """Register a transport implementation."""
        cls._transports[name] = transport_class

    @classmethod
    def create_transport(cls, config: ServerConfig) -> BaseTransport:
        """Create transport instance based on configuration."""
        transport_name = config.transport

        if transport_name not in cls._transports:
            available = ", ".join(cls._transports.keys())
            raise ConfigurationError(
                f"Unknown transport '{transport_name}'. Available: {available}",
                transport_name,
            )

        transport_class = cls._transports[transport_name]
        return transport_class(config)

    @classmethod
    def get_available_transports(cls) -> list[str]:
        """Get list of available transport names."""
        return list(cls._transports.keys())

    @classmethod
    def configure_logging(cls, transport: str, level: str) -> None:
        """Configure logging per transport type."""
        from ..logging_config import configure_logging

        configure_logging(transport, level)
