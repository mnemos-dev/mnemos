"""Tests for mnemos.search — ChromaDB SearchEngine with 3-layer filtering."""
from __future__ import annotations

import pytest

from mnemos.config import MnemosConfig
from mnemos.search import SearchEngine


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def engine(config: MnemosConfig) -> SearchEngine:
    """In-memory SearchEngine for isolated tests."""
    return SearchEngine(config, in_memory=True)


# ---------------------------------------------------------------------------
# test_index_and_search
# ---------------------------------------------------------------------------


def test_index_and_search(engine: SearchEngine) -> None:
    """Index a drawer and verify it's found by semantic search."""
    engine.index_drawer(
        drawer_id="d1",
        text="Supabase RLS must be enabled on all tables.",
        metadata={"wing": "ProcureTrack", "room": "Supabase", "hall": "decisions"},
    )

    results = engine.search("row level security database", limit=5)

    assert len(results) >= 1
    ids = [r["drawer_id"] for r in results]
    assert "d1" in ids

    # Verify result structure
    hit = next(r for r in results if r["drawer_id"] == "d1")
    assert "text" in hit
    assert "metadata" in hit
    assert "score" in hit
    assert 0.0 <= hit["score"] <= 1.0


# ---------------------------------------------------------------------------
# test_search_with_wing_filter
# ---------------------------------------------------------------------------


def test_search_with_wing_filter(engine: SearchEngine) -> None:
    """Wing filter must narrow results to only the specified wing."""
    engine.index_drawer(
        drawer_id="proc_d1",
        text="Supabase RLS policy for approval tables.",
        metadata={"wing": "ProcureTrack", "room": "Supabase", "hall": "decisions"},
    )
    engine.index_drawer(
        drawer_id="mnemos_d1",
        text="Supabase is also used in Mnemos for storage.",
        metadata={"wing": "Mnemos", "room": "Storage", "hall": "facts"},
    )

    # Search without filter — both should appear
    all_results = engine.search("Supabase", limit=10)
    all_ids = [r["drawer_id"] for r in all_results]
    assert "proc_d1" in all_ids
    assert "mnemos_d1" in all_ids

    # Search with wing filter — only ProcureTrack
    filtered = engine.search("Supabase", wing="ProcureTrack", limit=10)
    filtered_ids = [r["drawer_id"] for r in filtered]
    assert "proc_d1" in filtered_ids
    assert "mnemos_d1" not in filtered_ids


# ---------------------------------------------------------------------------
# test_search_with_hall_filter
# ---------------------------------------------------------------------------


def test_search_with_hall_filter(engine: SearchEngine) -> None:
    """Hall filter must return only drawers in the specified hall."""
    engine.index_drawer(
        drawer_id="dec_d1",
        text="Decision: use auth.uid() for user isolation.",
        metadata={"wing": "ProcureTrack", "room": "Auth", "hall": "decisions"},
    )
    engine.index_drawer(
        drawer_id="fact_d1",
        text="Fact: auth.uid() returns the current user UUID.",
        metadata={"wing": "ProcureTrack", "room": "Auth", "hall": "facts"},
    )

    # Filter to decisions hall only
    results = engine.search("auth uid user", hall="decisions", limit=10)
    result_ids = [r["drawer_id"] for r in results]
    assert "dec_d1" in result_ids
    assert "fact_d1" not in result_ids


# ---------------------------------------------------------------------------
# test_delete_drawer
# ---------------------------------------------------------------------------


def test_delete_drawer(engine: SearchEngine) -> None:
    """Deleting a drawer must remove it from search results."""
    engine.index_drawer(
        drawer_id="to_delete",
        text="This drawer will be deleted shortly.",
        metadata={"wing": "Mnemos", "room": "Temp", "hall": "facts"},
    )

    # Confirm it's indexed
    before = engine.search("deleted drawer", limit=5)
    before_ids = [r["drawer_id"] for r in before]
    assert "to_delete" in before_ids

    # Delete
    engine.delete_drawer("to_delete")

    # Confirm it's gone
    after = engine.search("deleted drawer", limit=5)
    after_ids = [r["drawer_id"] for r in after]
    assert "to_delete" not in after_ids


def test_delete_nonexistent_drawer(engine: SearchEngine) -> None:
    """Deleting a drawer that doesn't exist must not raise an error."""
    engine.delete_drawer("nonexistent_id")  # should not raise


# ---------------------------------------------------------------------------
# test_get_stats
# ---------------------------------------------------------------------------


def test_get_stats(engine: SearchEngine) -> None:
    """get_stats() must return correct total count and per-wing counts."""
    engine.index_drawer(
        drawer_id="p1",
        text="ProcureTrack drawer one.",
        metadata={"wing": "ProcureTrack", "room": "Supabase", "hall": "decisions"},
    )
    engine.index_drawer(
        drawer_id="p2",
        text="ProcureTrack drawer two.",
        metadata={"wing": "ProcureTrack", "room": "Auth", "hall": "facts"},
    )
    engine.index_drawer(
        drawer_id="m1",
        text="Mnemos drawer one.",
        metadata={"wing": "Mnemos", "room": "Core", "hall": "decisions"},
    )

    stats = engine.get_stats()

    assert stats["total_drawers"] == 3
    assert "wings" in stats
    assert stats["wings"]["ProcureTrack"] == 2
    assert stats["wings"]["Mnemos"] == 1
