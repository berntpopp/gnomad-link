"""Unified server manager for gnomAD with multiple transport support."""

import asyncio
import signal
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP

from .api.client import UnifiedGnomadClient
from .api.routes import (
    clinvar_router,
    gene_router,
    liftover_router,
    mitochondrial_router,
    region_router,
    search_router,
    structural_variant_router,
    transcript_router,
    variant_router,
)
from .config import ServerConfig, settings
from .exceptions import ConfigurationError, MCPIntegrationError, StartupError
from .logging_config import configure_logging, get_server_logger
from .services.frequency_service import FrequencyService


class UnifiedServerManager:
    """Manages multiple transport protocols for gnomAD server."""

    def __init__(self):
        """Initialize the unified server manager with default state."""
        self.app: FastAPI | None = None
        self.mcp: FastMCP | None = None
        self.shutdown_event = asyncio.Event()
        self.logger = None
        self._cleanup_tasks = []
        self._current_transport = "unknown"

    async def create_fastapi_app(self, config: ServerConfig) -> FastAPI:
        """Create FastAPI application with proper lifecycle."""

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            """Manage application lifecycle - startup and shutdown."""
            self.logger.info("Starting gnomAD Unified Server...")
            self.logger.info(
                f"Cache configuration: size={settings.CACHE_SIZE}, "
                f"TTL={settings.CACHE_TTL_MINUTES}min"
            )

            # Instantiate services ONCE and store them in the application's shared state.
            api_client = UnifiedGnomadClient()
            app.state.frequency_service = FrequencyService(
                client=api_client,
                cache_size=settings.CACHE_SIZE,
                cache_ttl_minutes=settings.CACHE_TTL_MINUTES,
            )

            self.logger.info("Server startup complete")
            yield

            # Cleanup
            self.logger.info("Shutting down server...")
            # Add any cleanup logic here
            self.logger.info("Server shutdown complete")

        # Create FastAPI app
        app = FastAPI(
            title="gnomAD Unified Data Server",
            description=(
                "Provides a comprehensive REST API and a focused MCP toolset for gnomAD. "
                "Access REST API at / and MCP tools at /mcp"
            ),
            version="4.0.0",
            lifespan=lifespan,
            docs_url="/docs" if config.enable_docs else None,
            redoc_url="/redoc" if config.enable_docs else None,
        )

        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Include all routers
        app.include_router(variant_router)
        app.include_router(gene_router)
        app.include_router(clinvar_router)
        app.include_router(liftover_router)
        app.include_router(structural_variant_router)
        app.include_router(mitochondrial_router)
        app.include_router(region_router)
        app.include_router(transcript_router)
        app.include_router(search_router)

        # Add utility endpoints
        self._add_utility_endpoints(app)

        return app

    def _add_utility_endpoints(self, app: FastAPI) -> None:
        """Add utility endpoints to FastAPI app."""
        from fastapi import Depends

        from .api.routes.dependencies import get_service

        @app.get("/", operation_id="get_root")
        async def root() -> dict[str, Any]:
            """Root endpoint providing API information."""
            return {
                "message": "gnomAD Unified Data Server",
                "version": "4.0.0",
                "interfaces": {
                    "rest_api": {
                        "docs": "/docs",
                        "health": "/health",
                        "cache_stats": "/cache/stats",
                    },
                    "mcp_tools": {
                        "endpoint": "/mcp",
                        "transport": "Streamable HTTP",
                    },
                },
                "configuration": {
                    "transport": getattr(self, "_current_transport", "unknown"),
                    "mcp_endpoint": (settings.mcp_url if hasattr(settings, "mcp_url") else None),
                },
            }

        @app.get("/health", operation_id="health_check")
        async def health_check() -> dict[str, str]:
            """Health check endpoint."""
            return {
                "status": "healthy",
                "transport": getattr(self, "_current_transport", "unknown"),
            }

        @app.get("/cache/stats", tags=["Monitoring"], operation_id="get_cache_stats")
        async def cache_stats(
            service: FrequencyService = Depends(get_service),
        ) -> dict[str, Any]:
            """Get cache statistics for monitoring."""
            return service.get_cache_stats()

        @app.post("/cache/clear", tags=["Monitoring"], operation_id="clear_cache")
        async def clear_cache(
            service: FrequencyService = Depends(get_service),
        ) -> dict[str, str]:
            """Clear the variant cache."""
            service.clear_cache()
            return {"status": "cache_cleared"}

    async def create_mcp_server(self, app: FastAPI, config: ServerConfig) -> FastMCP:
        """Create FastMCP server from FastAPI app."""
        try:
            # Import MCP configuration
            from fastmcp.server.providers.openapi import MCPType, RouteMap

            # Define custom names for tools to make them more LLM-friendly
            mcp_custom_names = {
                "get_variant_frequency_data": "get_variant_frequencies",
                "search_variants": "search_variants",
                "get_variant_by_position": "get_variant_by_position",
                "get_gene_details": "get_gene_details",
                "search_genes": "search_genes",
                "search_transcripts": "search_transcripts",
                "get_transcript_exons": "get_transcript_exons",
                "search_structural_variants": "get_structural_variants",
                "search_clinvar_variants": "search_clinvar_variants",
                "get_clinvar_variant": "get_clinvar_variant_details",
            }

            # Define routing rules to exclude certain endpoints from MCP
            mcp_route_maps = [
                # Exclude health and monitoring endpoints
                RouteMap(pattern=r"^/health$", mcp_type=MCPType.EXCLUDE),
                RouteMap(pattern=r"^/cache/.*$", mcp_type=MCPType.EXCLUDE),
                # Exclude root and docs endpoints
                RouteMap(pattern=r"^/$", mcp_type=MCPType.EXCLUDE),
                RouteMap(pattern=r"^/docs$", mcp_type=MCPType.EXCLUDE),
                RouteMap(pattern=r"^/openapi.json$", mcp_type=MCPType.EXCLUDE),
                RouteMap(pattern=r"^/redoc$", mcp_type=MCPType.EXCLUDE),
            ]

            # Create MCP server
            mcp = FastMCP.from_fastapi(
                app=app,
                name="gnomAD Link Server",
                mcp_names=mcp_custom_names,
                route_maps=mcp_route_maps,
            )

            self.logger.info("MCP server created successfully")
            return mcp

        except Exception as e:
            raise MCPIntegrationError(f"Failed to create MCP server: {e}", "mcp") from e

    def _compose_mcp_lifespan(self, app: FastAPI, mcp_app) -> None:
        """Run FastAPI and mounted FastMCP lifespans together."""
        fastapi_lifespan = app.router.lifespan_context
        mcp_lifespan = mcp_app.lifespan

        @asynccontextmanager
        async def combined_lifespan(parent_app: FastAPI):
            async with fastapi_lifespan(parent_app):
                async with mcp_lifespan(mcp_app):
                    yield

        app.router.lifespan_context = combined_lifespan

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""

        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            asyncio.create_task(self._graceful_shutdown())

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    async def _initialize_app_state(self, app: FastAPI, config: ServerConfig) -> None:
        """Manually initialize FastAPI app state for STDIO mode."""
        self.logger.info("Initializing app state for STDIO mode...")
        self.logger.info(
            f"Cache configuration: size={settings.CACHE_SIZE}, TTL={settings.CACHE_TTL_MINUTES}min"
        )

        # Instantiate services and store them in the application's shared state
        api_client = UnifiedGnomadClient()
        app.state.frequency_service = FrequencyService(
            client=api_client,
            cache_size=settings.CACHE_SIZE,
            cache_ttl_minutes=settings.CACHE_TTL_MINUTES,
        )

        self.logger.info("App state initialization complete")

    async def _graceful_shutdown(self) -> None:
        """Perform graceful shutdown."""
        self.logger.info("Starting graceful shutdown...")

        # Set shutdown event
        self.shutdown_event.set()

        # Wait for cleanup tasks
        if self._cleanup_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._cleanup_tasks, return_exceptions=True),
                    timeout=settings.GRACEFUL_SHUTDOWN_TIMEOUT,
                )
            except TimeoutError:
                self.logger.warning("Graceful shutdown timeout exceeded")

        self.logger.info("Graceful shutdown complete")

    async def start_unified_server(self, config: ServerConfig) -> None:
        """Start server with FastAPI + MCP HTTP."""
        try:
            self._current_transport = "unified"
            configure_logging("unified", config.log_level)
            self.logger = get_server_logger("unified")

            self.logger.info(f"Starting unified server on {config.host}:{config.port}")

            # Create FastAPI app
            self.app = await self.create_fastapi_app(config)

            # Create and mount MCP server
            self.mcp = await self.create_mcp_server(self.app, config)
            mcp_http_app = self.mcp.http_app(path="/")
            self._compose_mcp_lifespan(self.app, mcp_http_app)
            self.app.mount(config.mcp_path, mcp_http_app)

            self.logger.info(f"MCP HTTP interface mounted at {config.mcp_path}")
            self.logger.info(f"REST API available at http://{config.host}:{config.port}")
            self.logger.info(
                f"MCP HTTP available at http://{config.host}:{config.port}{config.mcp_path}"
            )
            self.logger.info(f"API documentation at http://{config.host}:{config.port}/docs")

            # Setup signal handlers
            self._setup_signal_handlers()

            # Run server
            uvicorn_config = uvicorn.Config(
                app=self.app,
                host=config.host,
                port=config.port,
                log_level=config.log_level.lower(),
                access_log=True,
            )
            server = uvicorn.Server(uvicorn_config)
            await server.serve()

        except Exception as e:
            raise StartupError(f"Failed to start unified server: {e}", "unified") from e

    async def start_stdio_server(self, config: ServerConfig) -> None:
        """Start STDIO-only MCP server."""
        try:
            self._current_transport = "stdio"
            configure_logging("stdio", config.log_level)
            self.logger = get_server_logger("stdio")

            self.logger.info("Starting STDIO MCP server...")

            # Create FastAPI app (for MCP introspection)
            self.app = await self.create_fastapi_app(config)

            # Manually initialize app state for STDIO mode (since lifespan won't trigger)
            await self._initialize_app_state(self.app, config)

            # Create MCP server
            self.mcp = await self.create_mcp_server(self.app, config)

            self.logger.info("STDIO MCP server ready")

            # Run MCP server in STDIO mode (async version for existing event loop)
            await self.mcp.run_async(transport="stdio")

        except Exception as e:
            raise StartupError(f"Failed to start STDIO server: {e}", "stdio") from e

    async def start_http_only_server(self, config: ServerConfig) -> None:
        """Start FastAPI-only server (no MCP)."""
        try:
            self._current_transport = "http"
            configure_logging("http", config.log_level)
            self.logger = get_server_logger("http")

            self.logger.info(f"Starting HTTP-only server on {config.host}:{config.port}")

            # Create FastAPI app
            self.app = await self.create_fastapi_app(config)

            self.logger.info(f"REST API available at http://{config.host}:{config.port}")
            self.logger.info(f"API documentation at http://{config.host}:{config.port}/docs")

            # Setup signal handlers
            self._setup_signal_handlers()

            # Run server
            uvicorn_config = uvicorn.Config(
                app=self.app,
                host=config.host,
                port=config.port,
                log_level=config.log_level.lower(),
                access_log=True,
            )
            server = uvicorn.Server(uvicorn_config)
            await server.serve()

        except Exception as e:
            raise StartupError(f"Failed to start HTTP-only server: {e}", "http") from e

    async def start_server(self, config: ServerConfig) -> None:
        """Start server based on configuration."""
        if config.transport == "unified":
            await self.start_unified_server(config)
        elif config.transport == "stdio":
            await self.start_stdio_server(config)
        elif config.transport == "http":
            await self.start_http_only_server(config)
        else:
            raise ConfigurationError(f"Unknown transport: {config.transport}")
