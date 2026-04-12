"""Tests for mnemos.stack — L0-L3 memory stack with wake_up."""
from __future__ import annotations

from pathlib import Path

import pytest

from mnemos.config import MnemosConfig
from mnemos.obsidian import write_drawer_file
from mnemos.palace import Palace
from mnemos.stack import MemoryStack


# ---------------------------------------------------------------------------
# test_l0_identity
# ---------------------------------------------------------------------------


def test_l0_identity(config: MnemosConfig) -> None:
    """recall(L0) loads Identity/L0-identity.md body."""
    palace = Palace(config)
    palace.ensure_structure()

    identity_file = config.identity_full_path / "L0-identity.md"
    write_drawer_file(
        identity_file,
        metadata={"type": "identity"},
        body="I am the memory palace. My purpose is to remember.",
    )

    stack = MemoryStack(config)
    result = stack.recall(level="L0")

    assert result["level"] == "L0"
    assert "I am the memory palace" in result["content"]
    assert result["token_count"] >= 1


# ---------------------------------------------------------------------------
# test_l1_wing_summaries
# ---------------------------------------------------------------------------


def test_l1_wing_summaries(config: MnemosConfig) -> None:
    """recall(L1) concatenates all _wing.md summaries."""
    palace = Palace(config)
    palace.ensure_structure()

    palace.create_wing("ProcureTrack")
    palace.create_wing("Mnemos")

    stack = MemoryStack(config)
    result = stack.recall(level="L1")

    assert result["level"] == "L1"
    assert "ProcureTrack" in result["content"]
    assert "Mnemos" in result["content"]
    assert result["token_count"] >= 1


# ---------------------------------------------------------------------------
# test_l2_wing_detail
# ---------------------------------------------------------------------------


def test_l2_wing_detail(config: MnemosConfig) -> None:
    """recall(L2, wing=...) concatenates _room.md summaries for that wing."""
    palace = Palace(config)
    palace.ensure_structure()

    palace.create_wing("ProcureTrack")
    palace.create_room("ProcureTrack", "Supabase")
    palace.create_room("ProcureTrack", "Frontend")

    stack = MemoryStack(config)
    result = stack.recall(level="L2", wing="ProcureTrack")

    assert result["level"] == "L2"
    assert "Supabase" in result["content"]
    assert "Frontend" in result["content"]
    assert result["token_count"] >= 1


# ---------------------------------------------------------------------------
# test_wake_up
# ---------------------------------------------------------------------------


def test_wake_up(config: MnemosConfig) -> None:
    """wake_up() returns combined identity + wings_summary."""
    palace = Palace(config)
    palace.ensure_structure()

    identity_file = config.identity_full_path / "L0-identity.md"
    write_drawer_file(
        identity_file,
        metadata={"type": "identity"},
        body="Core identity: I remember everything.",
    )

    palace.create_wing("ProcureTrack")

    stack = MemoryStack(config)
    result = stack.wake_up()

    assert "identity" in result
    assert "wings_summary" in result
    assert "token_count" in result

    assert "Core identity" in result["identity"]
    assert "ProcureTrack" in result["wings_summary"]
    assert result["token_count"] >= 1
