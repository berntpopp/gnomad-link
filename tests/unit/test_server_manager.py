from gnomad_link.server_manager import UnifiedServerManager


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
