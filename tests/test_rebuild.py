"""Tests for atomic rebuild infrastructure."""
from __future__ import annotations

from pathlib import Path

import pytest

from mnemos.config import MnemosConfig
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
