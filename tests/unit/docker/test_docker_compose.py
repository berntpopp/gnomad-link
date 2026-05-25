"""Docker Compose configuration regression tests."""

from __future__ import annotations

from pathlib import Path

BASE = Path("docker/docker-compose.yml").read_text(encoding="utf-8")
DEV = Path("docker/docker-compose.dev.yml").read_text(encoding="utf-8")
PROD = Path("docker/docker-compose.prod.yml").read_text(encoding="utf-8")
NPM = Path("docker/docker-compose.npm.yml").read_text(encoding="utf-8")
DOCKER_ENV = Path(".env.docker.example").read_text(encoding="utf-8")


def test_base_compose_runs_unified_http_mcp_service() -> None:
    assert "name: gnomad-link" in BASE
    assert "gnomad-link:" in BASE
    assert "MCP_TRANSPORT: unified" in BASE
    assert "MCP_PATH: /mcp" in BASE
    assert "${GNOMAD_LINK_HOST_PORT:-8020}:8000" in BASE
    assert '["gnomad-link", "--transport", "unified"' in BASE
    assert "http://localhost:8000/health" in BASE


def test_base_compose_loads_local_and_docker_env_files() -> None:
    assert "path: ../.env" in BASE
    assert "path: ../.env.docker" in BASE
    assert "required: false" in BASE


def test_development_overlay_bind_mounts_source() -> None:
    assert "target: builder" in DEV
    assert "../gnomad_link:/home/app/web/gnomad_link:delegated" in DEV
    assert "pip install -e ." in DEV


def test_production_overlay_has_container_hardening() -> None:
    assert "read_only: true" in PROD
    assert "no-new-privileges:true" in PROD
    assert "cap_drop:" in PROD
    assert "- ALL" in PROD
    assert "/tmp/gnomad-link:rw,noexec,nosuid,size=64m,mode=1777" in PROD  # noqa: S108
    assert "ports: !reset []" in PROD


def test_npm_overlay_uses_external_proxy_network_without_host_ports() -> None:
    assert "ports: !reset []" in NPM
    assert "npm-network:" in NPM
    assert "external: true" in NPM
    assert "${NPM_NETWORK_NAME:-npm_network}" in NPM


def test_docker_env_template_matches_compose_contract() -> None:
    assert "GNOMAD_LINK_HOST_PORT=8020" in DOCKER_ENV
    assert "MCP_TRANSPORT=unified" in DOCKER_ENV
    assert "MCP_HOST=0.0.0.0" in DOCKER_ENV
    assert "MCP_PATH=/mcp" in DOCKER_ENV
    assert "NPM_NETWORK_NAME=npm_network" in DOCKER_ENV
