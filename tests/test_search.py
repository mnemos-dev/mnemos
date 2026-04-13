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


# ---------------------------------------------------------------------------
# test_raw_doc_id — static helper
# ---------------------------------------------------------------------------


def test_raw_doc_id_deterministic() -> None:
    """raw_doc_id must return the same ID for the same inputs."""
    id1 = SearchEngine.raw_doc_id("/vault/Sessions/2026-04-10.md")
    id2 = SearchEngine.raw_doc_id("/vault/Sessions/2026-04-10.md")
    assert id1 == id2
    assert len(id1) == 64  # SHA-256 hex digest length


def test_raw_doc_id_chunk_distinct() -> None:
    """raw_doc_id with different chunk_index must produce different IDs."""
    base = "/vault/Sessions/2026-04-10.md"
    id_no_chunk = SearchEngine.raw_doc_id(base)
    id_chunk_0 = SearchEngine.raw_doc_id(base, chunk_index=0)
    id_chunk_1 = SearchEngine.raw_doc_id(base, chunk_index=1)
    assert id_no_chunk != id_chunk_0
    assert id_chunk_0 != id_chunk_1


# ---------------------------------------------------------------------------
# test_index_raw and raw search
# ---------------------------------------------------------------------------


def test_index_raw_and_search(engine: SearchEngine) -> None:
    """index_raw() must make documents findable via search(collection='raw')."""
    doc_id = SearchEngine.raw_doc_id("/vault/Sessions/2026-04-10.md", chunk_index=0)
    engine.index_raw(
        doc_id=doc_id,
        text="Row Level Security must be enabled on all Supabase tables.",
        metadata={"wing": "ProcureTrack", "source": "Sessions/2026-04-10.md"},
    )

    results = engine.search("row level security database", collection="raw", limit=5)

    assert len(results) >= 1
    ids = [r["drawer_id"] for r in results]
    assert doc_id in ids

    hit = next(r for r in results if r["drawer_id"] == doc_id)
    assert "text" in hit
    assert "metadata" in hit
    assert "score" in hit
    assert 0.0 <= hit["score"] <= 1.0


def test_raw_collection_independent_from_mined(engine: SearchEngine) -> None:
    """Documents indexed in raw must not appear in mined searches and vice versa."""
    engine.index_drawer(
        drawer_id="mined_doc",
        text="Mined knowledge fragment about authentication.",
        metadata={"wing": "ProcureTrack", "room": "Auth", "hall": "decisions"},
    )
    engine.index_raw(
        doc_id=SearchEngine.raw_doc_id("/vault/raw.md"),
        text="Raw verbatim content about authentication tokens.",
        metadata={"wing": "ProcureTrack"},
    )

    mined_results = engine.search("authentication", collection="mined", limit=10)
    mined_ids = [r["drawer_id"] for r in mined_results]
    assert "mined_doc" in mined_ids
    assert SearchEngine.raw_doc_id("/vault/raw.md") not in mined_ids

    raw_results = engine.search("authentication", collection="raw", limit=10)
    raw_ids = [r["drawer_id"] for r in raw_results]
    assert SearchEngine.raw_doc_id("/vault/raw.md") in raw_ids
    assert "mined_doc" not in raw_ids


# ---------------------------------------------------------------------------
# test_rrf_merge (collection="both")
# ---------------------------------------------------------------------------


def test_rrf_merge_both_collections(engine: SearchEngine) -> None:
    """collection='both' must return results from mined and raw merged via RRF."""
    engine.index_drawer(
        drawer_id="mined_rrf",
        text="Supabase RLS policy for procurement approval tables.",
        metadata={"wing": "ProcureTrack", "room": "Supabase", "hall": "decisions"},
    )
    engine.index_raw(
        doc_id=SearchEngine.raw_doc_id("/vault/rrf.md"),
        text="Raw file: Supabase row level security configuration.",
        metadata={"wing": "ProcureTrack"},
    )

    results = engine.search("Supabase row level security", collection="both", limit=10)
    ids = [r["drawer_id"] for r in results]

    assert "mined_rrf" in ids
    assert SearchEngine.raw_doc_id("/vault/rrf.md") in ids


def test_rrf_score_calculation() -> None:
    """_rrf_score must implement sum(1/(k+rank)) correctly."""
    # Single rank=1, k=60 → 1/61
    assert abs(SearchEngine._rrf_score([1], k=60) - 1 / 61) < 1e-9
    # Two ranks: 1/(60+1) + 1/(60+2)
    expected = 1 / 61 + 1 / 62
    assert abs(SearchEngine._rrf_score([1, 2], k=60) - expected) < 1e-9
    # k default is 60
    assert SearchEngine._rrf_score([1]) == SearchEngine._rrf_score([1], k=60)


def test_rrf_both_returns_unique_docs(engine: SearchEngine) -> None:
    """A doc appearing in both collections must appear only once in RRF results."""
    # Index the same text content into both collections under different IDs
    engine.index_drawer(
        drawer_id="shared_topic_mined",
        text="Machine learning model for NLP classification tasks.",
        metadata={"wing": "ML", "room": "NLP", "hall": "facts"},
    )
    engine.index_raw(
        doc_id="shared_topic_raw",
        text="Machine learning NLP classification overview.",
        metadata={"wing": "ML"},
    )

    results = engine.search("NLP machine learning", collection="both", limit=10)
    result_ids = [r["drawer_id"] for r in results]

    # No duplicates
    assert len(result_ids) == len(set(result_ids))


# ---------------------------------------------------------------------------
# test_$in filter support
# ---------------------------------------------------------------------------


def test_search_with_wing_list_in_filter(engine: SearchEngine) -> None:
    """wing as a list must use $in and return results from any matching wing."""
    engine.index_drawer(
        drawer_id="wing_a",
        text="Alpha project database design.",
        metadata={"wing": "Alpha", "room": "DB", "hall": "decisions"},
    )
    engine.index_drawer(
        drawer_id="wing_b",
        text="Beta project database schema.",
        metadata={"wing": "Beta", "room": "DB", "hall": "decisions"},
    )
    engine.index_drawer(
        drawer_id="wing_c",
        text="Gamma project unrelated data.",
        metadata={"wing": "Gamma", "room": "Other", "hall": "facts"},
    )

    results = engine.search("database", wing=["Alpha", "Beta"], limit=10)
    result_ids = [r["drawer_id"] for r in results]

    assert "wing_a" in result_ids
    assert "wing_b" in result_ids
    assert "wing_c" not in result_ids


def test_search_with_hall_list_in_filter(engine: SearchEngine) -> None:
    """hall as a list must use $in and return results from any matching hall."""
    engine.index_drawer(
        drawer_id="hall_dec",
        text="Authentication decision: use JWT tokens.",
        metadata={"wing": "Mnemos", "room": "Auth", "hall": "decisions"},
    )
    engine.index_drawer(
        drawer_id="hall_fact",
        text="Authentication fact: JWT expires in 1 hour.",
        metadata={"wing": "Mnemos", "room": "Auth", "hall": "facts"},
    )
    engine.index_drawer(
        drawer_id="hall_log",
        text="Authentication log entry for audit trail.",
        metadata={"wing": "Mnemos", "room": "Auth", "hall": "logs"},
    )

    results = engine.search("authentication", hall=["decisions", "facts"], limit=10)
    result_ids = [r["drawer_id"] for r in results]

    assert "hall_dec" in result_ids
    assert "hall_fact" in result_ids
    assert "hall_log" not in result_ids


# ---------------------------------------------------------------------------
# test_$nin filter via exclude_wing
# ---------------------------------------------------------------------------


def test_search_exclude_wing(engine: SearchEngine) -> None:
    """exclude_wing must suppress results from the specified wing ($nin)."""
    engine.index_drawer(
        drawer_id="include_me",
        text="Procurement data model overview.",
        metadata={"wing": "ProcureTrack", "room": "DB", "hall": "facts"},
    )
    engine.index_drawer(
        drawer_id="exclude_me",
        text="Procurement schema definition.",
        metadata={"wing": "Archived", "room": "DB", "hall": "facts"},
    )

    results = engine.search("procurement", exclude_wing="Archived", limit=10)
    result_ids = [r["drawer_id"] for r in results]

    assert "include_me" in result_ids
    assert "exclude_me" not in result_ids


def test_search_exclude_wing_list(engine: SearchEngine) -> None:
    """exclude_wing as a list must suppress results from all specified wings."""
    engine.index_drawer(
        drawer_id="keep",
        text="Active NLP research notes.",
        metadata={"wing": "Research", "room": "NLP", "hall": "facts"},
    )
    engine.index_drawer(
        drawer_id="drop_a",
        text="Archived NLP experiment results.",
        metadata={"wing": "Archived", "room": "NLP", "hall": "facts"},
    )
    engine.index_drawer(
        drawer_id="drop_b",
        text="Deprecated NLP model notes.",
        metadata={"wing": "Deprecated", "room": "NLP", "hall": "facts"},
    )

    results = engine.search(
        "NLP research", exclude_wing=["Archived", "Deprecated"], limit=10
    )
    result_ids = [r["drawer_id"] for r in results]

    assert "keep" in result_ids
    assert "drop_a" not in result_ids
    assert "drop_b" not in result_ids


# ---------------------------------------------------------------------------
# test_get_stats includes raw_documents
# ---------------------------------------------------------------------------


def test_get_stats_includes_raw_documents(engine: SearchEngine) -> None:
    """get_stats() must include raw_documents count reflecting raw collection size."""
    # Initially both are 0
    stats = engine.get_stats()
    assert "raw_documents" in stats
    assert stats["raw_documents"] == 0

    # Add two raw docs
    engine.index_raw(
        doc_id=SearchEngine.raw_doc_id("/vault/a.md"),
        text="Raw content A.",
        metadata={"wing": "Alpha"},
    )
    engine.index_raw(
        doc_id=SearchEngine.raw_doc_id("/vault/b.md"),
        text="Raw content B.",
        metadata={"wing": "Beta"},
    )

    stats = engine.get_stats()
    assert stats["raw_documents"] == 2
    assert stats["total_drawers"] == 0  # no mined docs indexed
