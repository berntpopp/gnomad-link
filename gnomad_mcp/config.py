"""Configuration settings for the gnomAD MCP server."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Configuration
    GNOMAD_API_URL: str = "https://gnomad.broadinstitute.org/api"

    # Cache Configuration
    CACHE_SIZE: int = 1024  # Maximum number of variants to cache
    CACHE_TTL_MINUTES: int = 60  # Cache time-to-live in minutes

    # Server Configuration
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = "*"  # Comma-separated list of allowed origins

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


# Global settings instance
settings = Settings()
