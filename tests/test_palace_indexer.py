"""Tests for mnemos.palace_indexer — frontmatter-authoritative re-indexing."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mnemos.palace_indexer import (
    IndexStats,
    index_palace,
    parse_drawer,
    walk_palace,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_drawer(
    palace: Path,
    wing: str,
    room: str,
    hall: str,
    name: str,
    *,
    source: str = "C:/vault/Sessions/x.md",
    importance: float = 0.5,
    language: str = "en",
    body: str = "# Title\n\n> Source: [[x]]\n\nContent here.",
    frontmatter_extra: dict[str, Any] | None = None,
) -> Path:
    d = palace / "wings" / wing / room / hall
    d.mkdir(parents=True, exist_ok=True)
    fm_extra = frontmatter_extra or {}
    extra_lines = "".join(f"{k}: {v}\n" for k, v in fm_extra.items())
    fm = (
        "---\n"
        f"wing: {wing}\n"
        f"room: {room}\n"
        f"hall: {hall}\n"
        f"source: {source}\n"
        f"importance: {importance}\n"
        f"language: {language}\n"
        f"{extra_lines}"
        "---\n\n"
    )
    p = d / name
    p.write_text(fm + body, encoding="utf-8")
    return p


class FakeBackend:
    """Minimal SearchBackend test double."""

    def __init__(self) -> None:
        self.dropped = 0
        self.bulk_calls: list[list[tuple[str, str, dict]]] = []
        self.solo_calls: list[tuple[str, str, dict]] = []

    def drop_and_reinit(self) -> None:
        self.dropped += 1

    def index_drawer(self, drawer_id: str, text: str, metadata: dict) -> None:
        self.solo_calls.append((drawer_id, text, metadata))

    def index_drawers_bulk(self, items: list[tuple[str, str, dict]]) -> None:
        self.bulk_calls.append(list(items))


# ---------------------------------------------------------------------------
# walk_palace
# ---------------------------------------------------------------------------


def test_walk_palace_empty_dir(tmp_path: Path) -> None:
    assert list(walk_palace(tmp_path)) == []


def test_walk_palace_returns_all_drawers(tmp_path: Path) -> None:
    _write_drawer(tmp_path, "W", "r", "decisions", "a.md")
    _write_drawer(tmp_path, "W", "r", "events", "b.md")
    _write_drawer(tmp_path, "X", "r", "problems", "c.md")

    files = {p.name for p in walk_palace(tmp_path)}
    assert files == {"a.md", "b.md", "c.md"}


def test_walk_palace_skips_leading_underscore(tmp_path: Path) -> None:
    _write_drawer(tmp_path, "W", "r", "decisions", "a.md")
    # Lazy summary files that must be skipped
    (tmp_path / "wings" / "W" / "_wing.md").write_text("summary", encoding="utf-8")
    (tmp_path / "wings" / "W" / "r" / "_room.md").write_text("summary", encoding="utf-8")
    (tmp_path / "wings" / "W" / "r" / "decisions" / "_hall.md").write_text("noise", encoding="utf-8")

    files = {p.name for p in walk_palace(tmp_path)}
    assert files == {"a.md"}


def test_walk_palace_handles_missing_wings_dir(tmp_path: Path) -> None:
    """A palace dir without wings/ should not crash — just yield nothing."""
    (tmp_path / "something-else.md").write_text("noise", encoding="utf-8")
    assert list(walk_palace(tmp_path)) == []


# ---------------------------------------------------------------------------
# parse_drawer
# ---------------------------------------------------------------------------


def test_parse_drawer_extracts_tuple(tmp_path: Path) -> None:
    p = _write_drawer(
        tmp_path, "Mnemos", "backend", "decisions", "sample.md",
        source="C:/v/Sessions/foo.md", importance=0.9, language="tr",
    )
    parsed = parse_drawer(p)
    assert parsed is not None
    drawer_id, text, metadata = parsed
    assert drawer_id == "sample"
    assert "Content here." in text
    assert metadata["wing"] == "Mnemos"
    assert metadata["room"] == "backend"
    assert metadata["hall"] == "decisions"
    assert metadata["source"] == "C:/v/Sessions/foo.md"
    assert metadata["source_path"] == "C:/v/Sessions/foo.md"
    assert metadata["language"] == "tr"
    assert metadata["importance"] == 0.9


def test_parse_drawer_returns_none_for_missing_required_fields(tmp_path: Path) -> None:
    # frontmatter lacks hall
    p = tmp_path / "broken.md"
    p.write_text("---\nwing: X\nroom: r\n---\n\nbody", encoding="utf-8")
    assert parse_drawer(p) is None


def test_parse_drawer_returns_none_for_no_frontmatter(tmp_path: Path) -> None:
    p = tmp_path / "plain.md"
    p.write_text("# just a markdown file\n\nno yaml.", encoding="utf-8")
    assert parse_drawer(p) is None


def test_parse_drawer_tolerates_malformed_importance(tmp_path: Path) -> None:
    p = _write_drawer(
        tmp_path, "W", "r", "decisions", "x.md",
        frontmatter_extra={"importance": "not-a-number"},
    )
    # The helper writes a second importance entry; parse must not crash,
    # and metadata must omit importance or default to the last valid value.
    # Rewrite with malformed importance only
    p.write_text(
        "---\nwing: W\nroom: r\nhall: decisions\nimportance: not-a-number\n---\n\nbody\n",
        encoding="utf-8",
    )
    parsed = parse_drawer(p)
    assert parsed is not None
    _, _, metadata = parsed
    # importance silently dropped when non-numeric
    assert "importance" not in metadata


def test_parse_drawer_defaults_language_to_en(tmp_path: Path) -> None:
    p = tmp_path / "no-lang.md"
    p.write_text(
        "---\nwing: W\nroom: r\nhall: events\n---\n\nbody\n",
        encoding="utf-8",
    )
    parsed = parse_drawer(p)
    assert parsed is not None
    _, _, metadata = parsed
    assert metadata["language"] == "en"


# ---------------------------------------------------------------------------
# index_palace
# ---------------------------------------------------------------------------


def test_index_palace_drops_and_bulk_indexes(tmp_path: Path) -> None:
    _write_drawer(tmp_path, "Mnemos", "r", "decisions", "a.md")
    _write_drawer(tmp_path, "Mnemos", "r", "events", "b.md")

    backend = FakeBackend()
    stats = index_palace(backend, tmp_path)

    assert stats.indexed == 2
    assert stats.skipped == 0
    assert stats.dropped_first is True
    assert backend.dropped == 1
    assert len(backend.bulk_calls) == 1
    items = backend.bulk_calls[0]
    names = {item[0] for item in items}
    assert names == {"a", "b"}


def test_index_palace_respects_drop_first_false(tmp_path: Path) -> None:
    _write_drawer(tmp_path, "W", "r", "decisions", "a.md")

    backend = FakeBackend()
    stats = index_palace(backend, tmp_path, drop_first=False)

    assert stats.dropped_first is False
    assert backend.dropped == 0
    assert stats.indexed == 1


def test_index_palace_skips_drawers_with_bad_frontmatter(tmp_path: Path) -> None:
    _write_drawer(tmp_path, "W", "r", "decisions", "good.md")
    bad = tmp_path / "wings" / "W" / "r" / "events" / "bad.md"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("no frontmatter here", encoding="utf-8")

    backend = FakeBackend()
    stats = index_palace(backend, tmp_path)

    assert stats.indexed == 1
    assert stats.skipped == 1
    assert any("bad.md" in e for e in stats.errors)


def test_index_palace_empty_palace_does_nothing(tmp_path: Path) -> None:
    backend = FakeBackend()
    stats = index_palace(backend, tmp_path)

    assert stats.indexed == 0
    assert stats.skipped == 0
    assert backend.dropped == 1  # drop still runs
    assert backend.bulk_calls == []
