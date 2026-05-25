"""Unified server manager for gnomAD Link."""

from __future__ import annotations

import asyncio
import signal
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP

from gnomad_link.api.client import UnifiedGnomadClient
from gnomad_link.config import ServerConfig, settings
from gnomad_link.exceptions import ConfigurationError, MCPIntegrationError, StartupError
from gnomad_link.logging_config import configure_logging, get_server_logger
from gnomad_link.mcp.facade import create_gnomad_mcp
from gnomad_link.services.frequency_service import FrequencyService


class UnifiedServerManager:
    def __init__(self) -> None:
        self.app: FastAPI | None = None
        self.mcp: FastMCP | None = None
        self.shutdown_event = asyncio.Event()
        self.logger = None
        self._current_transport = "unknown"

    # ---------------- service factory helpers ----------------

    def _create_frequency_service(self) -> FrequencyService:
        api_client = UnifiedGnomadClient()
        return FrequencyService(
            client=api_client,
            cache_size=settings.CACHE_SIZE,
            cache_ttl_minutes=settings.CACHE_TTL_MINUTES,
        )

    # ---------------- FastAPI host (health only) ----------------

    async def _create_fastapi_app(self, config: ServerConfig) -> FastAPI:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            self.logger.info("Starting gnomAD Link host application...")
            app.state.frequency_service = self._create_frequency_service()
            self.logger.info("Service ready")
            yield
            self.logger.info("Shutting down host application...")

        app = FastAPI(
            title="gnomAD Link MCP Host",
            description="Thin FastAPI host that exposes /health and mounts the MCP HTTP app at /mcp.",
            version="5.0.0",
            lifespan=lifespan,
            docs_url=None,
            redoc_url=None,
            openapi_url=None,
        )
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @app.get("/health")
        async def health() -> dict[str, str]:
            return {"status": "healthy", "transport": self._current_transport}

        return app

    # ---------------- MCP creation ----------------

    def _create_mcp_server(self, service_factory: Callable[[], FrequencyService]) -> FastMCP:
        try:
            mcp = create_gnomad_mcp(service_factory=service_factory)
            self.logger.info("MCP facade created")
            return mcp
        except Exception as e:
            raise MCPIntegrationError(f"Failed to create MCP server: {e}", "mcp") from e

    @staticmethod
    def _compose_lifespan(app: FastAPI, mcp_app: Any) -> None:
        fastapi_lifespan = app.router.lifespan_context
        mcp_lifespan = mcp_app.lifespan

        @asynccontextmanager
        async def combined(parent_app: FastAPI):
            async with fastapi_lifespan(parent_app):
                async with mcp_lifespan(mcp_app):
                    yield

        app.router.lifespan_context = combined

    # ---------------- signal handlers ----------------

    def _setup_signal_handlers(self) -> None:
        def handler(signum, _frame) -> None:
            self.logger.info(f"Received signal {signum}; shutting down...")
            self.shutdown_event.set()

        signal.signal(signal.SIGTERM, handler)
        signal.signal(signal.SIGINT, handler)

    # ---------------- entry points ----------------

    async def start_unified_server(self, config: ServerConfig) -> None:
        try:
            self._current_transport = "unified"
            configure_logging("unified", config.log_level)
            self.logger = get_server_logger("unified")

            self.app = await self._create_fastapi_app(config)

            def service_factory() -> FrequencyService:
                if self.app is None:
                    raise RuntimeError("FastAPI host not initialized")
                return self.app.state.frequency_service

            self.mcp = self._create_mcp_server(service_factory)
            mcp_http_app = self.mcp.http_app(path="/", stateless_http=True, json_response=True)
            self._compose_lifespan(self.app, mcp_http_app)
            self.app.mount(config.mcp_path, mcp_http_app)

            self.logger.info(f"MCP HTTP at http://{config.host}:{config.port}{config.mcp_path}")
            self.logger.info(f"Health at http://{config.host}:{config.port}/health")

            self._setup_signal_handlers()

            uvicorn_config = uvicorn.Config(
                app=self.app,
                host=config.host,
                port=config.port,
                log_level=config.log_level.lower(),
                access_log=True,
            )
            await uvicorn.Server(uvicorn_config).serve()
        except Exception as e:
            raise StartupError(f"Failed to start unified server: {e}", "unified") from e

    async def start_stdio_server(self, config: ServerConfig) -> None:
        try:
            self._current_transport = "stdio"
            configure_logging("stdio", config.log_level)
            self.logger = get_server_logger("stdio")

            service = self._create_frequency_service()
            self.mcp = self._create_mcp_server(lambda: service)
            await self.mcp.run_async(transport="stdio")
        except Exception as e:
            raise StartupError(f"Failed to start STDIO server: {e}", "stdio") from e

    async def start_server(self, config: ServerConfig) -> None:
        if config.transport in {"unified", "http"}:
            await self.start_unified_server(config)
        elif config.transport == "stdio":
            await self.start_stdio_server(config)
        else:
            raise ConfigurationError(f"Unknown transport: {config.transport}")
