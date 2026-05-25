"""Tests for CLI cache management subcommands."""

from __future__ import annotations

from argparse import Namespace
from unittest.mock import MagicMock, patch

import pytest

from gnomad_link.cli import handle_cache_clear_command, handle_cache_stats_command


def test_cache_stats_prints_table(capsys: pytest.CaptureFixture[str]) -> None:
    """cache stats command prints cache size information."""
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

    with patch("gnomad_link.cli.UnifiedServerManager") as mock_manager_cls:
        mock_manager_cls.return_value._create_frequency_service.return_value = mock_service
        handle_cache_stats_command(Namespace())

    output = capsys.readouterr().out
    assert "cache_size" in output.lower() or "size" in output.lower()


def test_cache_clear_succeeds(capsys: pytest.CaptureFixture[str]) -> None:
    """cache clear command clears the cache and prints confirmation."""
    mock_service = MagicMock()
    mock_service.clear_cache.return_value = None

    with patch("gnomad_link.cli.UnifiedServerManager") as mock_manager_cls:
        mock_manager_cls.return_value._create_frequency_service.return_value = mock_service
        handle_cache_clear_command(Namespace())

    mock_service.clear_cache.assert_called_once()
    output = capsys.readouterr().out
    assert "cleared" in output.lower()
