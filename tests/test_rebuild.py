"""Tests for atomic rebuild infrastructure."""
from __future__ import annotations

from pathlib import Path

import pytest

from mnemos.config import MnemosConfig
from mnemos.palace import Palace
from mnemos.search import SearchEngine


@pytest.mark.parametrize("backend_name", ["chromadb", "sqlite-vec"])
def test_drop_and_reinit_empties_collections(tmp_path: Path, backend_name: str):
    cfg = MnemosConfig(vault_path=str(tmp_path), search_backend=backend_name)
    cfg.palace_dir.mkdir(parents=True, exist_ok=True)

    backend = SearchEngine(cfg)
    try:
        backend.index_drawer(
            "drawer-1", "hello world",
            {"wing": "W", "room": "R", "hall": "facts", "source_path": "x.md", "language": "en"},
        )
        stats_before = backend.get_stats()
        assert stats_before.get("total_drawers", 0) >= 1

        backend.drop_and_reinit()

        stats_after = backend.get_stats()
        assert stats_after.get("total_drawers", 0) == 0
        assert stats_after.get("raw_documents", 0) == 0

        # Must be re-usable after drop
        backend.index_drawer(
            "drawer-2", "post-reinit text",
            {"wing": "W", "room": "R", "hall": "facts", "source_path": "y.md", "language": "en"},
        )
        stats_reuse = backend.get_stats()
        assert stats_reuse.get("total_drawers", 0) == 1
    finally:
        backend.close()


def test_backup_wings_atomic_move(tmp_path: Path):
    cfg = MnemosConfig(vault_path=str(tmp_path))
    cfg.palace_dir.mkdir(parents=True, exist_ok=True)
    (cfg.wings_dir / "W" / "R" / "facts").mkdir(parents=True)
    (cfg.wings_dir / "W" / "R" / "facts" / "sample.md").write_text("x", encoding="utf-8")

    palace = Palace(cfg)
    dest = palace.backup_wings(timestamp="2026-04-18T12-00-00")

    assert dest.exists()
    assert (dest / "W" / "R" / "facts" / "sample.md").exists()
    assert not cfg.wings_dir.exists()


def test_backup_wings_collision_suffix(tmp_path: Path):
    cfg = MnemosConfig(vault_path=str(tmp_path))
    cfg.palace_dir.mkdir(parents=True, exist_ok=True)
    ts = "2026-04-18T12-00-00"
    (cfg.recycled_full_path / f"wings-{ts}").mkdir(parents=True)

    cfg.wings_dir.mkdir(parents=True, exist_ok=True)
    (cfg.wings_dir / "placeholder.txt").write_text("a", encoding="utf-8")

    palace = Palace(cfg)
    dest = palace.backup_wings(timestamp=ts)

    assert dest.name.startswith(f"wings-{ts}")
    assert dest.name != f"wings-{ts}"  # suffix appended


def test_graph_reset_clears_triples_and_entities(tmp_path: Path):
    from mnemos.graph import KnowledgeGraph
    graph = KnowledgeGraph(tmp_path / "g.sqlite")
    graph.add_triple(
        subject="Mnemos", predicate="uses", obj="sqlite-vec",
        source_file="x.md",
    )

    graph.reset()

    count = graph._conn.execute("SELECT COUNT(*) FROM triples").fetchone()[0]
    assert count == 0
    count_e = graph._conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    assert count_e == 0
