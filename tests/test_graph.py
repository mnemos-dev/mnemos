"""Tests for mnemos.graph — SQLite temporal knowledge graph."""
from __future__ import annotations

from pathlib import Path

import pytest

from mnemos.graph import KnowledgeGraph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_graph(tmp_path: Path) -> KnowledgeGraph:
    return KnowledgeGraph(tmp_path / "test.db")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_add_entity(tmp_path: Path):
    """Add an entity and retrieve it by name."""
    kg = make_graph(tmp_path)
    try:
        kg.add_entity("Alice", "Person", {"role": "engineer"})
        entity = kg.get_entity("Alice")
        assert entity is not None
        assert entity["name"] == "Alice"
        assert entity["type"] == "Person"
        assert entity["properties"]["role"] == "engineer"
        assert "created_at" in entity
    finally:
        kg.close()


def test_add_triple(tmp_path: Path):
    """Add a triple and query entity to retrieve it."""
    kg = make_graph(tmp_path)
    try:
        kg.add_triple("Alice", "works_at", "Acme Corp", source_file="notes/alice.md")
        results = kg.query_entity("Alice")
        assert len(results) == 1
        r = results[0]
        assert r["predicate"] == "works_at"
        assert r["object"] == "Acme Corp"
        assert r["source_file"] == "notes/alice.md"
        assert r["confidence"] == 1.0
    finally:
        kg.close()


def test_temporal_query(tmp_path: Path):
    """as_of filtering: OldTech valid Jan–Mar, NewTech from Mar onwards."""
    kg = make_graph(tmp_path)
    try:
        # OldTech: valid Jan 1 through Mar 1
        kg.add_triple(
            "Alice", "uses_tech", "OldTech",
            valid_from="2026-01-01",
            valid_to="2026-03-01",
        )
        # NewTech: valid from Mar 1, no end date
        kg.add_triple(
            "Alice", "uses_tech", "NewTech",
            valid_from="2026-03-01",
            valid_to=None,
        )

        # Query as of Feb — should get OldTech only
        feb_results = kg.query_entity("Alice", as_of="2026-02-01")
        objects_feb = [r["object"] for r in feb_results]
        assert "OldTech" in objects_feb
        assert "NewTech" not in objects_feb

        # Query as of Apr — should get NewTech only
        apr_results = kg.query_entity("Alice", as_of="2026-04-01")
        objects_apr = [r["object"] for r in apr_results]
        assert "NewTech" in objects_apr
        assert "OldTech" not in objects_apr
    finally:
        kg.close()


def test_timeline(tmp_path: Path):
    """timeline() returns all triples with valid_from, ordered chronologically."""
    kg = make_graph(tmp_path)
    try:
        kg.add_triple("Bob", "role", "intern", valid_from="2025-01-01", valid_to="2025-06-01")
        kg.add_triple("Bob", "role", "junior", valid_from="2025-06-01", valid_to="2026-01-01")
        kg.add_triple("Bob", "role", "senior", valid_from="2026-01-01")
        # Triple with no valid_from should be excluded
        kg.add_triple("Bob", "location", "HQ")

        tl = kg.timeline("Bob")
        # Only the 3 with valid_from
        assert len(tl) == 3
        dates = [t["valid_from"] for t in tl]
        assert dates == sorted(dates), "timeline should be ordered by valid_from ASC"
        assert tl[0]["object"] == "intern"
        assert tl[1]["object"] == "junior"
        assert tl[2]["object"] == "senior"
    finally:
        kg.close()


def test_delete_triples_by_source(tmp_path: Path):
    """delete_triples_by_source removes only triples matching source_file."""
    kg = make_graph(tmp_path)
    try:
        kg.add_triple("Carol", "knows", "Dave", source_file="file_a.md")
        kg.add_triple("Carol", "knows", "Eve", source_file="file_b.md")
        kg.add_triple("Carol", "knows", "Frank", source_file="file_a.md")

        deleted = kg.delete_triples_by_source("file_a.md")
        assert deleted == 2

        remaining = kg.query_entity("Carol")
        assert len(remaining) == 1
        assert remaining[0]["object"] == "Eve"
        assert remaining[0]["source_file"] == "file_b.md"
    finally:
        kg.close()
