"""Dockerfile hardening regression tests."""

from __future__ import annotations

from pathlib import Path

DOCKERFILE = Path("docker/Dockerfile").read_text(encoding="utf-8")


def test_dockerfile_uses_modern_python_and_uv_lock() -> None:
    digest = (
        "python:3.14-slim@sha256:b877e50bd90de10af8d82c57a022fc2e0dc731c5320d762a27986facfc3355c1"
    )
    assert f"FROM {digest} AS builder" in DOCKERFILE
    assert f"FROM {digest} AS production" in DOCKERFILE
    assert "COPY uv.lock pyproject.toml README.md ./" in DOCKERFILE
    assert "uv sync --frozen --no-dev --active --no-install-project" in DOCKERFILE


def test_dockerfile_runs_as_non_root_with_runtime_dirs() -> None:
    assert "USER app" in DOCKERFILE
    assert "/tmp/gnomad-link" in DOCKERFILE  # noqa: S108
    assert "/var/cache/gnomad-link" in DOCKERFILE


def test_dockerfile_serves_unified_http_mcp_by_default() -> None:
    assert 'CMD ["gnomad-link", "serve", "--transport", "unified"' in DOCKERFILE
    assert '"--host", "0.0.0.0"' in DOCKERFILE
    assert "MCP_PATH=/mcp" in DOCKERFILE


def test_dockerfile_has_no_image_level_healthcheck() -> None:
    for line in DOCKERFILE.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            assert not stripped.upper().startswith("HEALTHCHECK")


def test_dockerfile_pins_uv_and_has_no_floating_pip_upgrade() -> None:
    text = Path("docker/Dockerfile").read_text(encoding="utf-8")
    assert "pip install --upgrade" not in text, "floating pip/uv upgrade must be removed"
    assert (
        "ghcr.io/astral-sh/uv:0.8.7@sha256:"
        "1e26f9a868360eeb32500a35e05787ffff3402f01a8dc8168ef6aee44aef0aab" in text
    )
