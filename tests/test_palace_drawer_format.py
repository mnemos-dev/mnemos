"""Tests for drawer filename (source-date) and body template."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from mnemos.palace import (
    _extract_source_date,
    _slugify,
    _unique_filename,
)


def test_extract_source_date_from_filename_prefix(tmp_path: Path):
    src = tmp_path / "2026-04-13-phase-0-foundation.md"
    src.write_text("# 2026-04-13 — Phase 0 Foundation\n\nText.", encoding="utf-8")
    assert _extract_source_date(src) == "2026-04-13"


def test_extract_source_date_from_frontmatter_when_filename_missing(tmp_path: Path):
    src = tmp_path / "random-name.md"
    src.write_text(
        "---\ndate: 2026-04-10\n---\n# Title\n", encoding="utf-8",
    )
    assert _extract_source_date(src) == "2026-04-10"


def test_extract_source_date_falls_back_to_mtime(tmp_path: Path):
    src = tmp_path / "no-date-anywhere.md"
    src.write_text("# Hello", encoding="utf-8")
    target_ts = time.mktime((2026, 3, 1, 12, 0, 0, 0, 0, -1))
    os.utime(src, (target_ts, target_ts))
    assert _extract_source_date(src) == "2026-03-01"


def test_slugify_strips_leading_date_prefix():
    assert _slugify("2026-04-13 — Phase 0 Foundation Implementation") == \
        "phase-0-foundation-implementation"
    assert _slugify("2026-04-13-Mnemos v0.1") == "mnemos-v01"


def test_slugify_word_boundary_truncate():
    result = _slugify(
        "Mnemos Phase 0 Foundation Implementation Design Document Details",
        max_len=40,
    )
    assert len(result) <= 40
    assert not result.endswith("-")


def test_unique_filename_uses_source_date(tmp_path: Path):
    src = tmp_path / "2026-04-13-mnemos-session.md"
    src.write_text("# 2026-04-13 — Mnemos Phase 0\n\nBody.", encoding="utf-8")

    hall_dir = tmp_path / "hall"
    hall_dir.mkdir()

    title_text = "2026-04-13 — Mnemos Phase 0"
    filename = _unique_filename(hall_dir, source_date="2026-04-13", slug_text=title_text)
    assert filename.startswith("2026-04-13-")
    assert "2026-04-13-2026-04-13" not in filename
    assert filename.endswith(".md")


from mnemos.miner import _first_sentence


def test_first_sentence_full_sentence():
    text = "We decided to use sqlite-vec. It scores identical to chromadb."
    assert _first_sentence(text) == "We decided to use sqlite-vec."


def test_first_sentence_long_truncated_at_80():
    text = "This is an extremely long opening statement that definitely goes beyond the eighty character limit for drawer titles."
    result = _first_sentence(text, max_len=80)
    assert len(result) <= 80
    assert not result.endswith(" ")


def test_first_sentence_no_punctuation_returns_first_chunk():
    text = "no punctuation here just flowing prose that keeps going and going"
    result = _first_sentence(text, max_len=80)
    assert len(result) <= 80


def test_add_drawer_body_has_h1_and_source_wikilink(tmp_path: Path):
    from mnemos.config import MnemosConfig
    from mnemos.palace import Palace

    cfg = MnemosConfig(vault_path=str(tmp_path))
    palace = Palace(cfg)
    palace.ensure_structure()

    src_path = tmp_path / "Sessions" / "2026-04-13-demo-session.md"
    src_path.parent.mkdir(parents=True, exist_ok=True)
    src_path.write_text("# Demo Session\n\nExample body.", encoding="utf-8")

    drawer_path = palace.add_drawer(
        wing="Demo", room="session-log", hall="decisions",
        text="We picked sqlite-vec for its parity. The benchmark confirmed R@5.",
        source=str(src_path), importance=0.5, entities=["Demo"], language="en",
    )

    content = drawer_path.read_text(encoding="utf-8")
    assert "# We picked sqlite-vec for its parity." in content
    assert "> From [[2026-04-13-demo-session]]" in content
    assert "· decisions" in content
    assert "· 2026-04-13" in content
    assert "We picked sqlite-vec for its parity. The benchmark confirmed R@5." in content


def test_add_drawer_manual_source_omits_wikilink(tmp_path: Path):
    """When source is a synthetic string like 'manual' (mnemos_add MCP),
    the body must not carry a dead [[manual]] wikilink."""
    from mnemos.config import MnemosConfig
    from mnemos.palace import Palace

    cfg = MnemosConfig(vault_path=str(tmp_path))
    palace = Palace(cfg)
    palace.ensure_structure()

    drawer_path = palace.add_drawer(
        wing="Demo", room="general", hall="facts",
        text="A quick note added by hand via the MCP tool.",
        source="manual", importance=0.5, entities=[], language="en",
    )

    content = drawer_path.read_text(encoding="utf-8")
    assert "[[manual]]" not in content
    assert "[[unknown]]" not in content
    assert "From [[" not in content  # No wikilink line at all for synthetic sources
    assert "# A quick note added by hand via the MCP tool." in content
    # Blockquote still carries hall + date for context, just no dead wikilink
    assert "> facts" in content
