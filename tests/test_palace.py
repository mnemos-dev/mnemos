"""Tests for mnemos.palace — Wing/Room/Hall structure management with recycle."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from mnemos.config import MnemosConfig
from mnemos.palace import Palace


# ---------------------------------------------------------------------------
# test_ensure_structure
# ---------------------------------------------------------------------------


def test_ensure_structure(config: MnemosConfig) -> None:
    """ensure_structure() creates Wings/, Identity/, and _recycled/ directories."""
    palace = Palace(config)
    palace.ensure_structure()

    assert config.wings_dir.exists()
    assert config.identity_full_path.exists()
    assert config.recycled_full_path.exists()


# ---------------------------------------------------------------------------
# test_create_wing
# ---------------------------------------------------------------------------


def test_create_wing(config: MnemosConfig) -> None:
    """create_wing() creates wing dir (summary written lazily on first drawer)."""
    palace = Palace(config)
    palace.ensure_structure()

    wing_path = palace.create_wing("ProcureTrack")

    assert wing_path.is_dir()
    assert wing_path.name == "ProcureTrack"
    assert not (wing_path / "_wing.md").exists(), "_wing.md written lazily on first drawer"


# ---------------------------------------------------------------------------
# test_create_room
# ---------------------------------------------------------------------------


def test_create_room(config: MnemosConfig) -> None:
    """create_room() creates room dir (summaries and halls created lazily on first drawer)."""
    palace = Palace(config)
    palace.ensure_structure()
    palace.create_wing("ProcureTrack")

    room_path = palace.create_room("ProcureTrack", "Supabase")

    assert room_path.is_dir()
    assert room_path.name == "Supabase"
    assert not (room_path / "_room.md").exists(), "_room.md written lazily on first drawer"

    # Hall subdirs are NOT pre-created; they are created on first drawer
    for hall in config.halls:
        assert not (room_path / hall).is_dir(), f"Hall subdir {hall} should NOT be pre-created"


# ---------------------------------------------------------------------------
# test_add_drawer
# ---------------------------------------------------------------------------


def test_add_drawer(config: MnemosConfig) -> None:
    """add_drawer() creates a .md file in the correct hall directory."""
    palace = Palace(config)
    palace.ensure_structure()

    drawer_path = palace.add_drawer(
        wing="ProcureTrack",
        room="Supabase",
        hall="decisions",
        text="RLS is mandatory on all tables.",
        source="Sessions/2026-04-10-procuretrack.md",
        importance=5,
        entities=["Supabase", "RLS"],
        language="en",
    )

    # File must exist inside the correct hall directory
    assert drawer_path.exists()
    assert drawer_path.suffix == ".md"
    expected_dir = config.wings_dir / "ProcureTrack" / "Supabase" / "decisions"
    assert drawer_path.parent == expected_dir

    # Filename must start with the source's date (2026-04-10 from the
    # source filename prefix) — source-date filenames, v0.3.2 problem 7.
    assert drawer_path.name.startswith("2026-04-10")

    # Wing and room auto-created if they didn't exist
    assert (config.wings_dir / "ProcureTrack").is_dir()
    assert (config.wings_dir / "ProcureTrack" / "Supabase").is_dir()


# ---------------------------------------------------------------------------
# test_list_wings
# ---------------------------------------------------------------------------


def test_list_wings(config: MnemosConfig) -> None:
    """list_wings() returns all wing directory names."""
    palace = Palace(config)
    palace.ensure_structure()

    palace.create_wing("ProcureTrack")
    palace.create_wing("Mnemos")

    wings = palace.list_wings()

    assert isinstance(wings, list)
    assert "ProcureTrack" in wings
    assert "Mnemos" in wings
    assert len(wings) == 2


# ---------------------------------------------------------------------------
# test_list_drawers
# ---------------------------------------------------------------------------


def test_list_drawers(config: MnemosConfig) -> None:
    """list_drawers() returns drawer .md files, excluding _wing.md/_room.md."""
    palace = Palace(config)
    palace.ensure_structure()

    # Add two drawers in the same wing/room
    palace.add_drawer(
        wing="ProcureTrack",
        room="Supabase",
        hall="decisions",
        text="RLS is mandatory.",
        source="src1.md",
        importance=5,
        entities=[],
        language="en",
    )
    palace.add_drawer(
        wing="ProcureTrack",
        room="Supabase",
        hall="facts",
        text="auth.uid() isolates users.",
        source="src2.md",
        importance=3,
        entities=["auth.uid()"],
        language="en",
    )

    all_drawers = palace.list_drawers()
    assert len(all_drawers) == 2

    # Filter by wing
    wing_drawers = palace.list_drawers(wing="ProcureTrack")
    assert len(wing_drawers) == 2

    # Filter by wing + room
    room_drawers = palace.list_drawers(wing="ProcureTrack", room="Supabase")
    assert len(room_drawers) == 2

    # _wing.md and _room.md must NOT appear
    names = [p.name for p in all_drawers]
    assert "_wing.md" not in names
    assert "_room.md" not in names


# ---------------------------------------------------------------------------
# test_recycle_drawer
# ---------------------------------------------------------------------------


def test_recycle_drawer(config: MnemosConfig) -> None:
    """recycle_drawer() moves the drawer to _recycled/ with a date prefix."""
    palace = Palace(config)
    palace.ensure_structure()

    drawer_path = palace.add_drawer(
        wing="ProcureTrack",
        room="Supabase",
        hall="decisions",
        text="Decision to be recycled.",
        source="src.md",
        importance=4,
        entities=[],
        language="tr",
    )

    assert drawer_path.exists()

    recycled_path = palace.recycle_drawer(drawer_path)

    # Original must be gone
    assert not drawer_path.exists()

    # Recycled file must exist in _recycled/
    assert recycled_path.exists()
    assert recycled_path.parent == config.recycled_full_path

    # Must have a date prefix
    today = date.today().isoformat()
    assert recycled_path.name.startswith(today)


# ---------------------------------------------------------------------------
# test_wing_case_insensitive (regression: Mnemos vs mnemos split bug)
# ---------------------------------------------------------------------------


def test_create_wing_case_insensitive_reuses_existing(config: MnemosConfig) -> None:
    """Creating a wing whose name differs only in case must reuse the existing one.

    Regression: frontmatter 'project:' field with inconsistent casing across
    source files used to produce two separate wing directories (Mnemos vs
    mnemos), splitting drawers across both.
    """
    palace = Palace(config)
    palace.ensure_structure()

    first = palace.create_wing("Mnemos")
    second = palace.create_wing("mnemos")

    assert first == second
    wings = palace.list_wings()
    assert wings.count("Mnemos") == 1
    assert "mnemos" not in wings


def test_add_drawer_case_insensitive_reuses_wing(config: MnemosConfig) -> None:
    """add_drawer() must route to the existing wing regardless of input case."""
    palace = Palace(config)
    palace.ensure_structure()
    palace.create_wing("Mnemos")

    drawer = palace.add_drawer(
        wing="mnemos",
        room="backend",
        hall="facts",
        text="sqlite-vec backend ChromaDB'den daha dayanıklı.",
        source="src.md",
        importance=3,
        entities=[],
        language="tr",
    )

    # Must land inside the canonical "Mnemos" wing, not a new "mnemos" dir
    assert "Mnemos" in drawer.parts
    assert "mnemos" not in drawer.parts
    assert palace.list_wings() == ["Mnemos"]
