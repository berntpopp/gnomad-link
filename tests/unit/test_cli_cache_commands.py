"""Tests for the typer cache management subcommands (Standard v1)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from gnomad_link.cli import app

runner = CliRunner()


def test_cache_group_no_args_shows_help() -> None:
    """`cache` with no subcommand shows help listing stats/clear."""
    result = runner.invoke(app, ["cache"])
    assert result.exit_code != 0  # no_args_is_help exits non-zero
    assert "stats" in result.output
    assert "clear" in result.output


def test_cache_stats_prints_sizes() -> None:
    """`cache stats` prints cache size information."""
    mock_service = MagicMock()
    mock_service.get_cache_stats.return_value = {
        "hits": 10,
        "misses": 2,
        "total": 12,
        "hit_rate": 0.833,
        "cache_info": {
            "variant": {"currsize": 5, "maxsize": 1024, "hits": 10, "misses": 2},
            "gene": {"currsize": 1, "maxsize": 256, "hits": 0, "misses": 0},
        },
    }

    with patch("gnomad_link.server_manager.UnifiedServerManager") as mock_manager_cls:
        mock_manager_cls.return_value._create_frequency_service.return_value = mock_service
        result = runner.invoke(app, ["cache", "stats"])

    assert result.exit_code == 0
    assert "cache_size" in result.output.lower() or "size" in result.output.lower()
    mock_service.get_cache_stats.assert_called_once()


def test_cache_clear_succeeds() -> None:
    """`cache clear` clears the cache and prints confirmation."""
    mock_service = MagicMock()
    mock_service.clear_cache.return_value = None

    with patch("gnomad_link.server_manager.UnifiedServerManager") as mock_manager_cls:
        mock_manager_cls.return_value._create_frequency_service.return_value = mock_service
        result = runner.invoke(app, ["cache", "clear"])

    assert result.exit_code == 0
    mock_service.clear_cache.assert_called_once()
    assert "cleared" in result.output.lower()
