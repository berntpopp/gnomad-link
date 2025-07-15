#!/usr/bin/env python
"""Unified gnomAD server with multiple transport support.

Single entry point supporting FastAPI REST API, MCP HTTP, and MCP STDIO transports.
"""

import asyncio
import sys

from gnomad_link.cli import create_config_from_args, create_parser
from gnomad_link.exceptions import ConfigurationError, StartupError
from gnomad_link.server_manager import UnifiedServerManager


async def async_main(args) -> None:
    """Async main entry point."""
    try:
        # Create configuration
        config = create_config_from_args(args)

        # Create and start server
        manager = UnifiedServerManager()
        await manager.start_server(config)

    except KeyboardInterrupt:
        print("\nShutdown requested by user")
        sys.exit(0)
    except ConfigurationError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)
    except StartupError as e:
        print(f"Startup error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


def main() -> None:
    """Start the gnomAD unified server with specified transport."""
    # Parse command line arguments
    parser = create_parser()
    args = parser.parse_args()

    # Handle subcommands
    if args.command in ["config", "health"]:
        from gnomad_link.cli import main as cli_main

        cli_main()
        return

    # Handle server startup
    if args.transport == "stdio":
        # STDIO transport runs synchronously
        try:
            config = create_config_from_args(args)
            manager = UnifiedServerManager()

            # Run STDIO server directly (synchronous)
            asyncio.run(manager.start_stdio_server(config))

        except Exception as e:
            print(f"STDIO server error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # HTTP-based transports run asynchronously
        asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
