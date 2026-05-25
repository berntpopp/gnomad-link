"""Command line interface for gnomAD unified server."""

import argparse
import sys
from typing import Any

import httpx

from .config import ServerConfig, settings
from .server_manager import UnifiedServerManager


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for the server."""
    parser = argparse.ArgumentParser(
        description="gnomAD Unified Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Transport Options:
  unified  - FastAPI REST API + MCP HTTP (default)
  http     - FastAPI REST API only
  stdio    - MCP STDIO only (for AI assistants)

Examples:
  # Start unified server (REST + MCP HTTP)
  uv run python server.py --transport unified --port 8000

  # Start hosted MCP endpoint for AI assistant integration
  uv run python server.py --transport unified --port 8000

  # Start REST API only
  uv run python server.py --transport http --port 8000

  # Development mode with auto-reload
  uv run python server.py --transport unified --dev

  # Custom MCP path
  uv run python server.py --transport unified --mcp-path /api/mcp
        """,
    )

    parser.add_argument(
        "--transport",
        choices=["unified", "http", "stdio"],
        default="unified",
        help="Transport mode (default: unified)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )
    parser.add_argument(
        "--mcp-path",
        default="/mcp",
        help="MCP endpoint path (default: /mcp)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log level (default: INFO)",
    )
    parser.add_argument(
        "--disable-docs",
        action="store_true",
        help="Disable API documentation endpoints",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Development mode (enable auto-reload)",
    )

    # Add subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Config command
    config_parser = subparsers.add_parser("config", help="Show configuration")
    config_parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate configuration",
    )

    # Health command
    health_parser = subparsers.add_parser("health", help="Check server health")
    health_parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000",
        help="Server URL to check (default: http://127.0.0.1:8000)",
    )

    # Cache command group
    cache_parser = subparsers.add_parser("cache", help="In-process cache management")
    cache_subparsers = cache_parser.add_subparsers(dest="cache_command", help="Cache subcommands")
    cache_subparsers.add_parser("stats", help="Show cache statistics")
    cache_subparsers.add_parser("clear", help="Clear all caches and reset counters")

    return parser


def create_config_from_args(args: argparse.Namespace) -> ServerConfig:
    """Create server configuration from command line arguments."""
    return ServerConfig(
        transport=args.transport,
        host=args.host,
        port=args.port,
        mcp_path=args.mcp_path,
        enable_docs=not args.disable_docs,
        log_level=args.log_level,
    )


def handle_config_command(args: argparse.Namespace) -> None:
    """Handle config command."""
    config = create_config_from_args(args)

    print("=== gnomAD Server Configuration ===")
    print(f"Transport: {config.transport}")
    print(f"Host: {config.host}")
    print(f"Port: {config.port}")
    print(f"MCP Path: {config.mcp_path}")
    print(f"Enable Docs: {config.enable_docs}")
    print(f"Log Level: {config.log_level}")
    print()

    print("=== Environment Settings ===")
    print(f"GNOMAD_API_URL: {settings.GNOMAD_API_URL}")
    print(f"CACHE_SIZE: {settings.CACHE_SIZE}")
    print(f"CACHE_TTL_MINUTES: {settings.CACHE_TTL_MINUTES}")
    print(f"CORS_ORIGINS: {settings.CORS_ORIGINS}")
    print()

    if args.validate:
        print("=== Configuration Validation ===")
        try:
            # Basic validation
            if config.port < 1 or config.port > 65535:
                print("❌ Invalid port number")
                sys.exit(1)

            if config.transport == "unified" and not config.mcp_path.startswith("/"):
                print("❌ MCP path must start with '/'")
                sys.exit(1)

            print("✅ Configuration is valid")
        except Exception as e:
            print(f"❌ Configuration error: {e}")
            sys.exit(1)


def handle_health_command(args: argparse.Namespace) -> None:
    """Handle health command."""
    try:
        response = httpx.get(f"{args.url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("Server is healthy")
            print(f"Transport: {data.get('transport', 'unknown')}")
            print(f"Status: {data.get('status', 'unknown')}")
        else:
            print(f"Server returned status {response.status_code}")
            sys.exit(1)
    except httpx.HTTPError as e:
        print(f"Failed to connect to server: {e}")
        sys.exit(1)


def handle_cache_stats_command(args: argparse.Namespace) -> None:
    """Handle cache stats command."""
    service = UnifiedServerManager()._create_frequency_service()
    stats: dict[str, Any] = service.get_cache_stats()

    print("=== Cache Statistics ===")
    print(f"hits:       {stats['hits']}")
    print(f"misses:     {stats['misses']}")
    print(f"total:      {stats['total']}")
    print(f"hit_rate:   {stats['hit_rate']}")
    print()
    print("Cache sizes (currsize / maxsize):")
    for name, info in stats.get("cache_info", {}).items():
        currsize = info.get("currsize", 0)
        maxsize = info.get("maxsize", 0)
        print(f"  {name}: cache_size={currsize} / {maxsize}")


def handle_cache_clear_command(args: argparse.Namespace) -> None:
    """Handle cache clear command."""
    service = UnifiedServerManager()._create_frequency_service()
    service.clear_cache()
    print("Cache cleared and statistics reset.")


def main() -> None:
    """Execute CLI commands and handle arguments."""
    parser = create_parser()
    args = parser.parse_args()

    # Handle subcommands
    if args.command == "config":
        handle_config_command(args)
        return
    elif args.command == "health":
        handle_health_command(args)
        return
    elif args.command == "cache":
        if args.cache_command == "stats":
            handle_cache_stats_command(args)
        elif args.cache_command == "clear":
            handle_cache_clear_command(args)
        else:
            # Show cache subcommand help if no subcommand given
            parser.parse_args(["cache", "--help"])
        return

    # Default behavior: show help if no command specified
    if not hasattr(args, "transport"):
        parser.print_help()
        return

    # Return args for server startup
    return args


if __name__ == "__main__":
    main()
