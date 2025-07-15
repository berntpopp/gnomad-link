"""Logging configuration for gnomAD unified server."""

import logging
import sys
from typing import Optional

from .config import settings


class TransportAwareFormatter(logging.Formatter):
    """Formatter that includes transport context in log messages."""

    def format(self, record):
        """Format log record with transport context if available."""
        # Add transport context if available
        if hasattr(record, "transport"):
            record.msg = f"[{record.transport}] {record.msg}"
        return super().format(record)


def configure_logging(transport: str, level: Optional[str] = None) -> None:
    """Configure logging for specific transport."""
    # Determine log level based on transport
    if level is None:
        if transport == "stdio":
            level = settings.STDIO_LOG_LEVEL
        else:
            level = settings.MCP_LOG_LEVEL

    # Clear existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Configure formatter
    formatter = TransportAwareFormatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Configure handler based on transport
    if transport == "stdio":
        # STDIO transport: only stderr, minimal logging
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.WARNING)

        # Suppress verbose logging from libraries
        logging.getLogger("fastmcp").setLevel(logging.WARNING)
        logging.getLogger("fastmcp.utilities.openapi").setLevel(logging.WARNING)
        logging.getLogger("uvicorn").setLevel(logging.WARNING)
        logging.getLogger("fastapi").setLevel(logging.WARNING)
    else:
        # HTTP transports: normal logging
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, level.upper()))

    handler.setFormatter(formatter)

    # Configure root logger
    logging.root.setLevel(getattr(logging, level.upper()))
    logging.root.addHandler(handler)


def get_transport_logger(name: str, transport: str) -> logging.Logger:
    """Get a logger with transport context."""
    logger = logging.getLogger(name)

    class TransportLoggerAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            return f"[{transport}] {msg}", kwargs

    return TransportLoggerAdapter(logger, {})


# Pre-configured loggers for common use cases
def get_server_logger(transport: str) -> logging.Logger:
    """Get server logger with transport context."""
    return get_transport_logger("gnomad_server", transport)


def get_mcp_logger(transport: str) -> logging.Logger:
    """Get MCP logger with transport context."""
    return get_transport_logger("gnomad_mcp", transport)


def get_api_logger(transport: str) -> logging.Logger:
    """Get API logger with transport context."""
    return get_transport_logger("gnomad_api", transport)
