"""Tool-name compliance with the GeneFoundry Tool-Naming Standard v1.

Every registered tool must be unprefixed, snake_case, <= 50 chars, and start with
a canonical verb so it composes cleanly behind the ``genefoundry-router`` gateway,
which mounts this server under the ``gnomad`` namespace (tools surface as
``gnomad_<tool>``). Guards against future drift. See issue berntpopp/gnomad-link#8.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

_NAME_RE = re.compile(r"^[a-z0-9_]{1,50}$")
_CANONICAL_VERBS = frozenset({"get", "search", "list", "resolve", "find", "compare", "compute"})
_NAMESPACE = "gnomad"


def _no_service() -> Any:
    # Tool discovery only inspects the registered tool metadata; it never calls
    # the gnomAD service, so the factory must never be invoked here.
    raise AssertionError("tool-name discovery must not invoke the gnomAD service")


@pytest.mark.asyncio
async def test_tool_names_conform_to_standard_v1() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=_no_service)
    names = sorted(tool.name for tool in await mcp.list_tools())
    assert names, "no tools registered on the facade"
    for name in names:
        assert _NAME_RE.match(name), f"{name!r} must match ^[a-z0-9_]{{1,50}}$"
        assert name.split("_", 1)[0] in _CANONICAL_VERBS, (
            f"{name!r} must start with a canonical verb {sorted(_CANONICAL_VERBS)}"
        )
        assert not name.startswith(f"{_NAMESPACE}_"), (
            f"{name!r} must not self-prefix the '{_NAMESPACE}' namespace "
            "token — the gateway adds it"
        )
