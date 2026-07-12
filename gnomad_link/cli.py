"""Command line interface for gnomad-link (GeneFoundry CLI Standard v1).

A single ``typer`` application exposing ``serve``, ``config``, ``health``,
``cache``, and ``version``. The console script ``gnomad-link`` resolves to
:data:`app`; there is no bare-serve and no stdio transport (Streamable HTTP
only).
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import ServerConfig, settings

app = typer.Typer(
    name="gnomad-link",
    add_completion=False,
    no_args_is_help=True,
    help="gnomad-link — MCP server grounding variant/gene questions in gnomAD.",
)

cache_app = typer.Typer(
    name="cache",
    add_completion=False,
    no_args_is_help=True,
    help="In-process cache management.",
)
app.add_typer(cache_app)

console = Console()

TransportOption = typer.Option("unified", "--transport", help="Transport mode (unified or http).")


@app.command()
def serve(
    transport: str = TransportOption,
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind to."),
    port: int = typer.Option(8000, "--port", help="Port to bind to."),
    mcp_path: str = typer.Option("/mcp", "--mcp-path", help="MCP endpoint path."),
    log_level: str = typer.Option("INFO", "--log-level", help="Log level."),
    disable_docs: bool = typer.Option(False, "--disable-docs", help="Disable API docs."),
    dev: bool = typer.Option(False, "--dev", help="Development mode (console logs)."),
) -> None:
    """Start the unified FastAPI host (/health) with the MCP HTTP app at /mcp."""
    if transport not in {"unified", "http"}:
        console.print(f"[red]Invalid transport {transport!r}; choose 'unified' or 'http'.[/red]")
        raise typer.Exit(code=2)
    if not mcp_path.startswith("/"):
        console.print("[red]MCP path must start with '/'.[/red]")
        raise typer.Exit(code=2)

    config = ServerConfig(
        transport="unified" if transport == "unified" else "http",
        host=host,
        port=port,
        mcp_path=mcp_path,
        # The DNS-rebinding allowlists are environment-only (no CLI flag). Omitting them
        # here fell back to the loopback-only dataclass default, so a proxied deployment
        # answered every request with 421 regardless of MCP_ALLOWED_HOSTS.
        allowed_hosts=settings.MCP_ALLOWED_HOSTS,
        allowed_origins=settings.MCP_ALLOWED_ORIGINS,
        enable_docs=not disable_docs,
        log_level=log_level,
    )

    from .server_manager import UnifiedServerManager

    manager = UnifiedServerManager()
    try:
        asyncio.run(manager.start_server(config, dev=dev))
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutdown requested by user[/yellow]")
        raise typer.Exit(code=0) from None


@app.command()
def config(
    validate: bool = typer.Option(False, "--validate", help="Validate configuration."),
) -> None:
    """Show (and optionally validate) the resolved configuration."""
    cfg = ServerConfig.from_env()

    table = Table(title="gnomad-link configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("transport", cfg.transport)
    table.add_row("host", cfg.host)
    table.add_row("port", str(cfg.port))
    table.add_row("mcp_path", cfg.mcp_path)
    table.add_row("enable_docs", str(cfg.enable_docs))
    table.add_row("log_level", cfg.log_level)
    table.add_row("log_format", settings.LOG_FORMAT)
    table.add_row("gnomad_api_url", settings.GNOMAD_API_URL)
    table.add_row("cache_size", str(settings.CACHE_SIZE))
    table.add_row("cache_ttl_minutes", str(settings.CACHE_TTL_MINUTES))
    table.add_row("cors_origins", settings.CORS_ORIGINS)
    console.print(table)

    if validate:
        if cfg.port < 1 or cfg.port > 65535:
            console.print("[red]Invalid port number[/red]")
            raise typer.Exit(code=1)
        if not cfg.mcp_path.startswith("/"):
            console.print("[red]MCP path must start with '/'[/red]")
            raise typer.Exit(code=1)
        console.print("[green]Configuration is valid[/green]")


@app.command()
def health(
    url: str = typer.Option("http://127.0.0.1:8000", "--url", help="Server base URL to check."),
) -> None:
    """Check the running server's /health endpoint."""
    try:
        response = httpx.get(f"{url}/health", timeout=5)
    except httpx.HTTPError as exc:
        console.print(f"[red]Failed to connect to server: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    if response.status_code != 200:
        console.print(f"[red]Server returned status {response.status_code}[/red]")
        raise typer.Exit(code=1)
    data = response.json()
    console.print("[green]Server is healthy[/green]")
    console.print(f"Transport: {data.get('transport', 'unknown')}")
    console.print(f"Status: {data.get('status', 'unknown')}")


@cache_app.command("stats")
def cache_stats() -> None:
    """Show in-process cache statistics."""
    from .server_manager import UnifiedServerManager

    service = UnifiedServerManager()._create_frequency_service()
    stats: dict[str, Any] = service.get_cache_stats()

    table = Table(title="gnomad-link cache statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("hits", str(stats["hits"]))
    table.add_row("misses", str(stats["misses"]))
    table.add_row("total", str(stats["total"]))
    table.add_row("hit_rate", str(stats["hit_rate"]))
    console.print(table)

    sizes = Table(title="Cache sizes (currsize / maxsize)")
    sizes.add_column("Cache", style="cyan")
    sizes.add_column("cache_size", style="green")
    for name, info in stats.get("cache_info", {}).items():
        currsize = info.get("currsize", 0)
        maxsize = info.get("maxsize", 0)
        sizes.add_row(name, f"{currsize} / {maxsize}")
    console.print(sizes)


@cache_app.command("clear")
def cache_clear() -> None:
    """Clear all caches and reset counters."""
    from .server_manager import UnifiedServerManager

    service = UnifiedServerManager()._create_frequency_service()
    service.clear_cache()
    console.print("[green]Cache cleared and statistics reset.[/green]")


@app.command()
def version() -> None:
    """Print the gnomad-link version."""
    console.print(__version__)


if __name__ == "__main__":
    app()
