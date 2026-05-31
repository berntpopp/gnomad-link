"""Unit tests for gnomad_link.mcp.next_commands builders.

Contract enforced here:
  - Every next_commands entry is a dict {"tool": <non-empty str>, "arguments": <dict>}.
  - for_variant() entries always have a NON-EMPTY arguments dict; the
    non-empty contract is the CALLER's responsibility when using cmd() directly.
"""

from __future__ import annotations

from gnomad_link.mcp.next_commands import cmd, for_variant


def test_cmd_returns_expected_shape() -> None:
    result = cmd("get_variant_frequencies", variant_id="1-2-A-T", dataset="gnomad_r4")
    assert result == {
        "tool": "get_variant_frequencies",
        "arguments": {"variant_id": "1-2-A-T", "dataset": "gnomad_r4"},
    }


def test_cmd_allows_empty_arguments() -> None:
    # cmd() itself does NOT enforce non-empty arguments — that is the CALLER's
    # responsibility. This test documents the permissive behaviour of cmd().
    result = cmd("x")
    assert result == {"tool": "x", "arguments": {}}


def test_for_variant_returns_two_entries() -> None:
    entries = for_variant("1-2-A-T", "gnomad_r4")
    assert len(entries) == 2


def test_for_variant_first_entry_is_get_variant_frequencies() -> None:
    entries = for_variant("1-2-A-T", "gnomad_r4")
    first = entries[0]
    assert first["tool"] == "get_variant_frequencies"
    assert first["arguments"]["variant_id"] == "1-2-A-T"
    assert first["arguments"]["dataset"] == "gnomad_r4"


def test_for_variant_second_entry_is_get_clinvar_variant_details() -> None:
    entries = for_variant("1-2-A-T", "gnomad_r4")
    second = entries[1]
    assert second["tool"] == "get_clinvar_variant_details"
    assert second["arguments"]["variant_id"] == "1-2-A-T"


def test_for_variant_all_entries_have_non_empty_arguments() -> None:
    entries = for_variant("1-2-A-T", "gnomad_r4")
    for entry in entries:
        assert isinstance(entry["arguments"], dict), "arguments must be a dict"
        assert entry["arguments"], f"arguments must be non-empty for tool {entry['tool']!r}"
