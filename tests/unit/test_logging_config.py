"""Tests for the structlog-based logging configuration (Standard v1)."""

from __future__ import annotations

import json

import structlog

from gnomad_link import __version__
from gnomad_link.logging_config import configure_logging


def test_json_event_has_canonical_fields(capsys) -> None:
    """A JSON-rendered event carries level, timestamp, event, service, version."""
    configure_logging("INFO", "json")
    logger = structlog.get_logger("gnomad_link")
    logger.info("startup_complete")

    line = capsys.readouterr().out.strip().splitlines()[-1]
    event = json.loads(line)

    assert event["event"] == "startup_complete"
    assert event["level"] == "info"
    assert "timestamp" in event
    assert event["service"] == "gnomad-link"
    assert event["version"] == __version__


def test_correlation_id_is_bound_into_events(capsys) -> None:
    """A correlation id bound via contextvars is merged into every event."""
    configure_logging("INFO", "json")
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(correlation_id="abc-123")
    try:
        logger = structlog.get_logger("gnomad_link")
        logger.info("handled_request")
    finally:
        structlog.contextvars.clear_contextvars()

    line = capsys.readouterr().out.strip().splitlines()[-1]
    event = json.loads(line)
    assert event["correlation_id"] == "abc-123"


def test_console_format_is_not_json(capsys) -> None:
    """The dev console renderer emits human-readable (non-JSON) output."""
    configure_logging("DEBUG", "console")
    logger = structlog.get_logger("gnomad_link")
    logger.info("dev_event")

    out = capsys.readouterr().out
    assert "dev_event" in out
    # The console renderer does not produce a parseable JSON object.
    line = out.strip().splitlines()[-1]
    try:
        json.loads(line)
        parsed_as_json = True
    except json.JSONDecodeError:
        parsed_as_json = False
    assert parsed_as_json is False
