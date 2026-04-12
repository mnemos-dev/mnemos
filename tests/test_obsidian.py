"""Tests for mnemos.obsidian — frontmatter parsing and drawer file management."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mnemos.obsidian import parse_drawer_file, parse_frontmatter, write_drawer_file


# ---------------------------------------------------------------------------
# test_parse_frontmatter
# ---------------------------------------------------------------------------


def test_parse_frontmatter(tmp_path: Path) -> None:
    """Parse a .md file that has valid YAML frontmatter."""
    note = tmp_path / "note.md"
    note.write_text(
        "---\n"
        "title: Test Note\n"
        "tags: [foo, bar]\n"
        "importance: 3\n"
        "---\n"
        "\n"
        "# Hello\n"
        "\n"
        "Body text here.\n",
        encoding="utf-8",
    )

    meta, body = parse_frontmatter(note)

    assert meta["title"] == "Test Note"
    assert meta["tags"] == ["foo", "bar"]
    assert meta["importance"] == 3
    assert "# Hello" in body
    assert "Body text here." in body
    # frontmatter markers should NOT appear in body
    assert "---" not in body


def test_parse_frontmatter_no_frontmatter(tmp_path: Path) -> None:
    """Files without frontmatter return ({}, full_text)."""
    note = tmp_path / "plain.md"
    content = "# Just a plain note\n\nNo YAML here.\n"
    note.write_text(content, encoding="utf-8")

    meta, body = parse_frontmatter(note)

    assert meta == {}
    assert body == content


# ---------------------------------------------------------------------------
# test_write_drawer_file
# ---------------------------------------------------------------------------


def test_write_drawer_file(tmp_path: Path) -> None:
    """Write a drawer file and verify the roundtrip via parse_frontmatter."""
    filepath = tmp_path / "wing" / "room" / "fragment.md"
    metadata: dict[str, Any] = {
        "wing": "decisions",
        "room": "ProcureTrack",
        "hall": "decisions",
        "source": "Sessions/2026-04-10-procuretrack.md",
        "importance": 5,
        "language": "tr",
        "entities": ["Supabase", "RLS"],
    }
    body = "Supabase RLS tüm tablolarda zorunlu kılındı."

    write_drawer_file(filepath, metadata, body)

    assert filepath.exists()

    # roundtrip: parse back
    meta_rt, body_rt = parse_frontmatter(filepath)

    assert meta_rt["wing"] == "decisions"
    assert meta_rt["room"] == "ProcureTrack"
    assert meta_rt["importance"] == 5
    assert meta_rt["entities"] == ["Supabase", "RLS"]
    # mined_at must be injected automatically
    assert "mined_at" in meta_rt
    assert body.strip() in body_rt.strip()


# ---------------------------------------------------------------------------
# test_parse_drawer_file
# ---------------------------------------------------------------------------


def test_parse_drawer_file(tmp_path: Path) -> None:
    """parse_drawer_file returns a structured dict with all expected keys."""
    filepath = tmp_path / "decisions" / "ProcureTrack" / "rls-decision.md"
    metadata: dict[str, Any] = {
        "wing": "decisions",
        "room": "ProcureTrack",
        "hall": "decisions",
        "source": "Sessions/2026-04-10-procuretrack.md",
        "importance": 4,
        "language": "tr",
        "entities": ["Supabase", "RLS", "auth.uid()"],
        "mined_at": "2026-04-12T08:00:00",
    }
    body = "RLS politikaları auth.uid() ile kullanıcı izolasyonunu sağlar."
    write_drawer_file(filepath, metadata, body)

    result = parse_drawer_file(filepath)

    assert result["wing"] == "decisions"
    assert result["room"] == "ProcureTrack"
    assert result["hall"] == "decisions"
    assert result["source"] == "Sessions/2026-04-10-procuretrack.md"
    assert result["importance"] == 4
    assert result["language"] == "tr"
    assert result["entities"] == ["Supabase", "RLS", "auth.uid()"]
    assert result["mined_at"] == "2026-04-12T08:00:00"
    assert body.strip() in result["text"].strip()
    assert result["filepath"] == filepath
