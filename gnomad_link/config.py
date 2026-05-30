"""Configuration settings for the gnomAD unified server."""

from dataclasses import dataclass
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings


@dataclass
class ServerConfig:
    """Server configuration with transport selection."""

    transport: Literal["unified", "http", "stdio"] = "unified"
    host: str = "127.0.0.1"
    port: int = 8000
    mcp_path: str = "/mcp"
    enable_docs: bool = True
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "ServerConfig":
        """Create configuration from environment variables."""
        return cls(
            transport=settings.MCP_TRANSPORT,
            host=settings.MCP_HOST,
            port=settings.MCP_PORT,
            mcp_path=settings.MCP_PATH,
            enable_docs=settings.ENABLE_SWAGGER,
            log_level=settings.LOG_LEVEL,
        )


class Settings(BaseSettings):
    """Enhanced application settings with transport support."""

    # API Configuration
    GNOMAD_API_URL: str = "https://gnomad.broadinstitute.org/api"
    # Max concurrent in-flight upstream GraphQL requests per client. Bounds burst
    # pressure on gnomAD's rate limiter; the jittered retry layer absorbs residual
    # 429s. Keep conservative for the public endpoint; raise for trusted runs.
    GNOMAD_MAX_CONCURRENCY: int = 5
    # Per-request upstream timeout (seconds). Large-gene variant payloads (e.g. CFTR
    # ~13MB) complete in ~5-6s, but cold/slow responses need headroom; a too-tight
    # timeout would trip the retry layer and multiply wall-clock time.
    GNOMAD_REQUEST_TIMEOUT: int = 60

    # Cache Configuration
    CACHE_SIZE: int = 1024  # Maximum number of variants to cache
    CACHE_TTL_MINUTES: int = 60  # Cache time-to-live in minutes

    # Transport Configuration
    MCP_TRANSPORT: Literal["unified", "http", "stdio"] = "unified"
    MCP_HOST: str = "127.0.0.1"
    MCP_PORT: int = 8000
    MCP_PATH: str = "/mcp"

    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    MCP_LOG_LEVEL: str = "INFO"
    STDIO_LOG_LEVEL: str = "WARNING"  # Reduced for STDIO compatibility

    # Server Configuration
    CORS_ORIGINS: str = "*"  # Comma-separated list of allowed origins
    ENABLE_SWAGGER: bool = True
    ENABLE_MONITORING: bool = True

    # Production Configuration
    GRACEFUL_SHUTDOWN_TIMEOUT: int = 30
    MAX_PAGE_SIZE: int = 100

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, v: str) -> str:
        """Validate CORS origins format."""
        if not v or v == "*":
            return v
        # Basic validation for comma-separated origins
        origins = [origin.strip() for origin in v.split(",")]
        return ",".join(origins)

    @field_validator("MCP_PATH")
    @classmethod
    def validate_mcp_path(cls, v: str) -> str:
        """Ensure MCP path starts with /."""
        if not v.startswith("/"):
            return f"/{v}"
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        """Get CORS origins as a list."""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def mcp_url(self) -> str:
        """Get the full MCP URL."""
        return f"http://{self.MCP_HOST}:{self.MCP_PORT}{self.MCP_PATH}"


# Global settings instance
settings = Settings()
