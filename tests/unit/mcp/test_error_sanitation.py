"""Unit contract for the caller-visible message sanitizer.

`sanitize_message` is the defensive backstop applied to every caller-visible
error/message/diagnostics string: it strips the fence's forbidden
control/zero-width/bidi/NUL code points and length-caps the result, so a hostile
upstream (or a caller-influenced 4xx/5xx body) can never smuggle those code
points into an error frame. It must NOT strip ordinary whitespace (TAB/LF/CR).
"""

from __future__ import annotations

import pytest

from gnomad_link.mcp.untrusted_content import (
    FORBIDDEN_CODEPOINTS,
    MAX_MESSAGE_CHARS,
    sanitize_message,
)


@pytest.mark.parametrize("codepoint", sorted(FORBIDDEN_CODEPOINTS))
def test_every_forbidden_code_point_is_stripped(codepoint: int) -> None:
    """Each member of the ratified forbidden set is removed from a message."""
    char = chr(codepoint)
    clean = sanitize_message(f"before{char}after")
    assert char not in clean
    assert clean == "beforeafter"


@pytest.mark.parametrize("codepoint", [0x09, 0x0A, 0x0D])  # TAB, LF, CR
def test_ordinary_whitespace_survives(codepoint: int) -> None:
    """TAB / LF / CR are deliberately NOT in the forbidden set and must survive."""
    char = chr(codepoint)
    assert codepoint not in FORBIDDEN_CODEPOINTS
    assert char in sanitize_message(f"line1{char}line2")


def test_removes_nul_zwj_bom_and_bidi_override_together() -> None:
    clean = sanitize_message("boom\x00 zwj‍ bom﻿ rtl‮ tail")
    assert clean == "boom zwj bom rtl tail"


def test_preserves_ordinary_prose() -> None:
    text = "gnomAD upstream returned an error (2 error(s))."
    assert sanitize_message(text) == text


def test_length_capped() -> None:
    capped = sanitize_message("x" * 1000)
    assert len(capped) == MAX_MESSAGE_CHARS
    assert MAX_MESSAGE_CHARS <= 280
