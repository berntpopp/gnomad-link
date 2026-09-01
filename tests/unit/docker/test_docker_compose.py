"""Docker Compose configuration regression tests."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

BASE = Path("docker/docker-compose.yml").read_text(encoding="utf-8")
DEV = Path("docker/docker-compose.dev.yml").read_text(encoding="utf-8")
PROD = Path("docker/docker-compose.prod.yml").read_text(encoding="utf-8")
NPM = Path("docker/docker-compose.npm.yml").read_text(encoding="utf-8")
DOCKER_ENV = Path(".env.docker.example").read_text(encoding="utf-8")

NUMERIC_USER_RE = re.compile(r"^[1-9][0-9]*:[1-9][0-9]*$")


class _TagTolerantLoader(yaml.SafeLoader):
    """A SafeLoader that tolerates Compose's custom merge tags (``!reset``,
    ``!override``, ...) by resolving scalar nodes to their plain value and
    everything else to ``None``, since only the ``user`` key's presence and
    value matter to the guard tests below."""


_TagTolerantLoader.add_multi_constructor(
    "!",
    lambda loader, _suffix, node: (
        loader.construct_scalar(node) if isinstance(node, yaml.ScalarNode) else None
    ),
)


def test_base_compose_runs_unified_http_mcp_service() -> None:
    assert "name: gnomad-link" in BASE
    assert "gnomad-link:" in BASE
    assert "MCP_TRANSPORT: unified" in BASE
    assert "MCP_PATH: /mcp" in BASE
    assert "${GNOMAD_LINK_HOST_PORT:-8020}:8000" in BASE
    assert '["gnomad-link", "serve", "--transport", "unified"' in BASE
    assert "http://localhost:8000/health" in BASE


def test_base_compose_binds_published_ports_to_loopback() -> None:
    """Security guard: the base compose is dev/local-only and must loopback-bind
    every published host port (127.0.0.1). Docker otherwise binds 0.0.0.0 and
    bypasses the host firewall, exposing the unauthenticated backend on the
    public IP. Production reaches it only via the router/reverse proxy overlays
    (ports: !reset []). Research use only; not clinical decision support."""
    compose = yaml.safe_load(BASE)
    published = [
        (name, mapping)
        for name, svc in compose["services"].items()
        for mapping in (svc.get("ports") or [])
    ]
    assert published, "base compose should publish at least one host port for local/dev use"
    for name, mapping in published:
        assert isinstance(mapping, str), (
            f"{name} uses long-form ports; extend this guard to read host_ip"
        )
        assert mapping.startswith("127.0.0.1:"), (
            f"{name} publishes {mapping!r} on all interfaces; bind the "
            "unauthenticated backend to loopback (127.0.0.1) - Docker otherwise "
            "binds 0.0.0.0 and bypasses the host firewall. Production reaches it "
            "only via the router/reverse proxy."
        )


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
    assert "/tmp:rw,noexec,nosuid,size=64m,mode=1777" in PROD  # noqa: S108
    assert "ports: !reset []" in PROD


def test_npm_overlay_uses_external_proxy_network_without_host_ports() -> None:
    assert "ports: !reset []" in NPM
    assert "npm-network:" in NPM
    assert "external: true" in NPM
    assert "${NPM_NETWORK_NAME:-npm_default}" in NPM


def test_docker_env_template_matches_compose_contract() -> None:
    assert "GNOMAD_LINK_HOST_PORT=8020" in DOCKER_ENV
    assert "MCP_TRANSPORT=unified" in DOCKER_ENV
    assert "MCP_HOST=0.0.0.0" in DOCKER_ENV
    assert "MCP_PATH=/mcp" in DOCKER_ENV
    assert "NPM_NETWORK_NAME=npm_default" in DOCKER_ENV


def test_npm_overlay_declares_numeric_user_for_every_service() -> None:
    """The fleet controller's deploy contract wants every service in the
    deployed overlay to declare a numeric non-root ``user`` (its runtime
    observer proves the effective uid from /proc); the release gate below
    forbids the same key in the release Compose files."""
    # _TagTolerantLoader subclasses yaml.SafeLoader and only adds tolerance for
    # Compose's own custom tags (!reset, !override); it never gains the unsafe
    # arbitrary-object constructors ruff's S506 warns about.
    compose = yaml.load(NPM, Loader=_TagTolerantLoader)  # noqa: S506
    services = compose["services"]
    assert services, "docker-compose.npm.yml should declare at least one service"
    for name, svc in services.items():
        user = svc.get("user")
        assert user is not None, f"{name} does not declare a numeric user"
        assert NUMERIC_USER_RE.match(str(user)), (
            f"{name} user={user!r} is not numeric non-root (expected uid:gid)"
        )


def test_release_compose_files_never_declare_user() -> None:
    """`container-release.json` names the Compose files the release gate
    validates; none of them may declare `user` — the deployed uid:gid lives
    only in the NPM overlay that the fleet controller renders on top."""
    release_config = json.loads(Path("container-release.json").read_text(encoding="utf-8"))
    compose_files = release_config["service"]["compose_files"]
    assert compose_files, "container-release.json should list compose files"
    for compose_file in compose_files:
        text = Path(compose_file).read_text(encoding="utf-8")
        compose = yaml.load(text, Loader=_TagTolerantLoader)  # noqa: S506
        for name, svc in compose["services"].items():
            assert "user" not in svc, (
                f"{compose_file}: service {name} declares user; the release gate forbids it"
            )
