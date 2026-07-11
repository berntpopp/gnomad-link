"""Unit contract for the caller-visible message sanitizer.

`sanitize_message` is the defensive backstop applied to every caller-visible
error/message/diagnostics string: it strips the fence's forbidden
control/zero-width/bidi/NUL code points and length-caps the result, so a hostile
upstream (or a caller-influenced 4xx/5xx body) can never smuggle those code
points into an error frame.
"""

from __future__ import annotations

from gnomad_link.mcp.untrusted_content import MAX_MESSAGE_CHARS, sanitize_message


def test_removes_nul_zwj_bom_and_bidi_override() -> None:
    dirty = "boom\x00 zwj‍ bom﻿ rtl‮ tail"
    clean = sanitize_message(dirty)

    assert "\x00" not in clean
    assert "‍" not in clean  # zero-width joiner
    assert "﻿" not in clean  # byte-order mark
    assert "‮" not in clean  # right-to-left override
    # The surrounding ordinary prose is preserved (only code points are stripped).
    assert clean == "boom zwj bom rtl tail"


def test_preserves_ordinary_prose() -> None:
    text = "gnomAD upstream returned an error (2 error(s))."
    assert sanitize_message(text) == text


def test_length_capped() -> None:
    capped = sanitize_message("x" * 1000)
    assert len(capped) == MAX_MESSAGE_CHARS
    assert MAX_MESSAGE_CHARS <= 280
