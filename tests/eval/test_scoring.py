"""Unit tests for _valid_next_commands in tests.eval.scoring."""

from tests.eval.scoring import _valid_next_commands


def test_normal_tool_with_args_is_valid() -> None:
    result = _valid_next_commands(
        [
            {
                "tool": "get_variant_frequencies",
                "arguments": {"variant_id": "x", "dataset": "gnomad_r4"},
            }
        ]
    )
    assert result is True


def test_no_arg_tool_diagnostics_empty_args_is_valid() -> None:
    result = _valid_next_commands([{"tool": "get_gnomad_diagnostics", "arguments": {}}])
    assert result is True


def test_no_arg_tool_capabilities_empty_args_is_valid() -> None:
    result = _valid_next_commands([{"tool": "get_server_capabilities", "arguments": {}}])
    assert result is True


def test_regular_tool_empty_args_is_invalid() -> None:
    # search_genes REQUIRES a query; empty args are not directly callable
    result = _valid_next_commands([{"tool": "search_genes", "arguments": {}}])
    assert result is False


def test_empty_list_is_invalid() -> None:
    result = _valid_next_commands([])
    assert result is False


def test_non_list_is_invalid() -> None:
    result = _valid_next_commands("notalist")
    assert result is False


def test_empty_tool_name_is_invalid() -> None:
    result = _valid_next_commands([{"tool": "", "arguments": {"x": 1}}])
    assert result is False
