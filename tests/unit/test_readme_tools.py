"""The README's ``## Tools`` table must match the server's registered tools.

GeneFoundry README Standard v1, Rule 6: the tool table is machine-verified, not
hand-maintained. Adding, renaming, or removing a tool without updating the README
fails CI — which is what stops the table drifting into a lie.

The live tool list is enumerated exactly as ``test_tool_names.py`` does it: build
the facade with a service factory that must never be called, then ``list_tools()``.
Never hardcode the expected names here; that would defeat the purpose.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

README = Path(__file__).resolve().parents[2] / "README.md"

# A table row: | `tool_name` | purpose |
_ROW_RE = re.compile(r"^\|\s*`([a-z0-9_]+)`\s*\|")


def _no_service() -> Any:
    # Tool discovery only inspects registered tool metadata; it never calls the
    # gnomAD service, so the factory must never be invoked here.
    raise AssertionError("tool-name discovery must not invoke the gnomAD service")


def _readme_tool_names() -> set[str]:
    """Tool names listed in the README's '## Tools' table."""
    lines = README.read_text(encoding="utf-8").splitlines()

    try:
        start = lines.index("## Tools")
    except ValueError:  # pragma: no cover - guarded by the assertion below
        return set()

    names: set[str] = set()
    for line in lines[start + 1 :]:
        if line.startswith("## "):  # next section ends the table
            break
        match = _ROW_RE.match(line)
        if match:
            names.add(match.group(1))
    return names


@pytest.mark.asyncio
async def test_readme_tools_table_matches_registered_tools() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=_no_service)
    registered = {tool.name for tool in await mcp.list_tools()}
    assert registered, "no tools registered on the facade"

    documented = _readme_tool_names()
    assert documented, "no tool rows found in the README '## Tools' table"

    missing = registered - documented
    extra = documented - registered
    assert not missing, (
        f"tools registered but absent from the README '## Tools' table: {sorted(missing)}"
    )
    assert not extra, (
        f"tools listed in the README '## Tools' table but not registered: {sorted(extra)}"
    )
