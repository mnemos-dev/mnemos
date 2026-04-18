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
