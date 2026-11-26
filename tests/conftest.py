"""Pytest configuration and fixtures."""

import asyncio
import json
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastmcp import FastMCP
from jsonschema import Draft202012Validator

from gnomad_link.logging_config import configure_logging

# Configure structlog once for the test session (console renderer, quiet level).
configure_logging("WARNING", "console")


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


ENVELOPE_SCHEMA_PATH = Path(__file__).parent / "conformance" / "envelope-v1.2.schema.json"
_ENVELOPE = Draft202012Validator(json.loads(ENVELOPE_SCHEMA_PATH.read_text()))


def schema_errors(envelope: Any) -> list[str]:
    """Violations of the vendored Response-Envelope v1.2 schema in one envelope."""
    return [f"{e.json_path}: {e.message}" for e in _ENVELOPE.iter_errors(envelope)]


@pytest.fixture(name="schema_errors")
def _schema_errors_fixture() -> Any:
    return schema_errors


def envelope_errors(tool: str, envelope: Any) -> list[str]:
    """``schema_errors`` minus the one known gap."""
    errors = schema_errors(envelope)
    if tool == "get_clinvar_variant_details":
        # Known gap (#161): compact mode drops raw_sha256 / retrieved_at from its fenced
        # texts. test_envelope_v1_2.py pins it, so closing the gap fails there, not here.
        errors = [e for e in errors if not e.startswith("$.result.submissions")]
    return errors


@pytest.fixture(autouse=True)
def _every_tool_result_is_a_v1_2_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate every in-process tool result the suite produces against the schema.

    The services are stubbed per test file, so there is no single fixture set that
    drives every tool; checking each envelope the tests already produce covers all.
    """
    original = FastMCP.call_tool

    async def call_tool(self: FastMCP, name: str, *args: Any, **kwargs: Any) -> Any:
        result = await original(self, name, *args, **kwargs)
        envelope = getattr(result, "structured_content", None)
        if envelope is not None:
            assert not envelope_errors(name, envelope), (name, envelope_errors(name, envelope))
        return result

    monkeypatch.setattr(FastMCP, "call_tool", call_tool)
