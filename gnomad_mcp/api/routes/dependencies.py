"""Shared dependencies for FastAPI routes."""

from fastapi import Request

from gnomad_mcp.services import FrequencyService


def get_service(request: Request) -> FrequencyService:
    """Get the frequency service instance from app state."""
    return request.app.state.frequency_service
