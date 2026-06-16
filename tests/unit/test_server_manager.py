import asyncio

import pytest

from gnomad_link.config import ServerConfig
from gnomad_link.exceptions import ConfigurationError
from gnomad_link.server_manager import UnifiedServerManager


def test_start_server_rejects_unknown_transport() -> None:
    """start_server raises ConfigurationError for any non-HTTP transport (no stdio)."""
    config = ServerConfig(transport="unified")
    object.__setattr__(config, "transport", "stdio")  # simulate a stale stdio value
    manager = UnifiedServerManager()
    with pytest.raises(ConfigurationError):
        asyncio.run(manager.start_server(config))


def test_server_manager_uses_facade(monkeypatch) -> None:
    import gnomad_link.server_manager as sm

    called = {}

    def fake_create(*, service_factory):
        called["service_factory"] = service_factory
        return object()

    monkeypatch.setattr(sm, "create_gnomad_mcp", fake_create)
    manager = UnifiedServerManager()
    manager.logger = type("L", (), {"info": lambda *a, **k: None})()
    mcp = manager._create_mcp_server(lambda: None)
    assert mcp is not None
    assert callable(called["service_factory"])


def test_server_manager_no_longer_imports_fastmcp_from_fastapi() -> None:
    import inspect

    import gnomad_link.server_manager as sm

    source = inspect.getsource(sm)
    assert "from_fastapi" not in source
    assert "mcp_custom_names" not in source
    assert "RouteMap" not in source
