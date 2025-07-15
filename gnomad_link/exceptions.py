"""Custom exceptions for gnomAD unified server."""

from typing import Optional


class GnomadServerError(Exception):
    """Base exception for gnomAD server errors."""

    def __init__(self, message: str, transport: Optional[str] = None):
        """Initialize gnomAD server error with message and optional transport context."""
        super().__init__(message)
        self.transport = transport


class TransportError(GnomadServerError):
    """Exception for transport-related errors."""

    pass


class ConfigurationError(GnomadServerError):
    """Exception for configuration validation errors."""

    pass


class StartupError(GnomadServerError):
    """Exception for server startup errors."""

    pass


class ShutdownError(GnomadServerError):
    """Exception for server shutdown errors."""

    pass


class MCPIntegrationError(TransportError):
    """Exception for MCP integration errors."""

    pass


class HTTPTransportError(TransportError):
    """Exception for HTTP transport errors."""

    pass


class STDIOTransportError(TransportError):
    """Exception for STDIO transport errors."""

    pass
