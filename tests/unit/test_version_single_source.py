"""Guard: pyproject -> installed metadata -> __version__ -> serverInfo are one value.

The gnomAD Link package version is single-sourced from ``pyproject.toml``
(``[project].version``). ``gnomad_link.__version__`` is derived from the
installed distribution metadata, and the MCP ``initialize`` handshake must
advertise *that* package version in ``serverInfo.version`` -- not the FastMCP
framework version.
"""

from __future__ import annotations

import tomllib
from importlib.metadata import version
from pathlib import Path
from typing import Any

from gnomad_link import __version__
from gnomad_link.mcp.facade import create_gnomad_mcp

DIST = "gnomad-link"


def _pyproject_version() -> str:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    return tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]


def _no_service() -> Any:
    # Building the facade only registers tool metadata; it never constructs
    # the gnomAD service, so the factory must never be invoked here.
    raise AssertionError("facade construction must not invoke the gnomAD service")


def test_pyproject_is_the_single_source() -> None:
    assert version(DIST) == _pyproject_version()


def test_dunder_version_is_metadata_derived() -> None:
    assert __version__ == version(DIST)


def test_mcp_server_info_version_matches_package() -> None:
    assert create_gnomad_mcp(service_factory=_no_service).version == __version__
