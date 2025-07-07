"""Route dependencies for the unified server."""

from typing import TYPE_CHECKING, cast

from fastapi import Request

if TYPE_CHECKING:
    from gnomad_mcp.services.frequency_service import FrequencyService


def get_service(request: Request) -> "FrequencyService":
    """Get the frequency service instance from the request's app state.

    This function is used as a dependency in FastAPI routes to inject
    the shared FrequencyService instance.

    Args:
        request: The FastAPI request object

    Returns:
        The FrequencyService instance from app.state
    """
    return cast("FrequencyService", request.app.state.frequency_service)
