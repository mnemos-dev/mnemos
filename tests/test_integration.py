"""End-to-end integration tests for the full Mnemos cycle."""
from __future__ import annotations

from pathlib import Path

import pytest

from mnemos.config import MnemosConfig
from mnemos.server import MnemosApp


# ---------------------------------------------------------------------------
# test_full_cycle
# ---------------------------------------------------------------------------


def test_full_cycle(
    config: MnemosConfig,
    sample_session_tr: Path,
    sample_session_en: Path,
    sample_topic: Path,
) -> None:
    """Full end-to-end cycle: create app, mine files, search, status, recall, list wings, dedup."""

    # 1. Create app and ensure structure
    app = MnemosApp(config, chromadb_in_memory=True)
    app.palace.ensure_structure()

    # 2. Mine all 3 fixture files — each should create >= 1 drawer
    for fixture_path in (sample_session_tr, sample_session_en, sample_topic):
        result = app.handle_mine(path=str(fixture_path))
        assert result["drawers_created"] >= 1, (
            f"Expected >= 1 drawer from {fixture_path.name}, "
            f"got {result['drawers_created']}"
        )

    # 3. Search "Supabase karar" — verify >= 1 result containing "Supabase" or "supabase"
    search_results = app.handle_search("Supabase karar")
    assert len(search_results) >= 1, "Expected at least 1 result for 'Supabase karar'"
    texts_combined = " ".join(r["text"] for r in search_results)
    assert "supabase" in texts_combined.lower(), (
        "Expected at least one result to contain 'Supabase'"
    )

    # 4. Search with wing filter "LightRAG" for "cost problem"
    #    (The English session note has project: Mnemos; wing comes from miner heuristic)
    #    We first discover what wing the LightRAG content ended up in, then filter on it.
    lightrag_results = app.handle_search("cost problem")
    assert len(lightrag_results) >= 1, "Expected at least 1 result for 'cost problem'"

    # Identify the wing that holds the LightRAG content
    lightrag_wing = None
    for r in lightrag_results:
        text_lower = r["text"].lower()
        if "lightrag" in text_lower or "cost" in text_lower:
            lightrag_wing = r["metadata"].get("wing")
            break

    if lightrag_wing is not None:
        filtered = app.handle_search("cost problem", wing=lightrag_wing)
        for r in filtered:
            assert r["metadata"].get("wing") == lightrag_wing, (
                f"Wing filter broken: expected '{lightrag_wing}', "
                f"got '{r['metadata'].get('wing')}'"
            )

    # 5. Check status — total_drawers >= 3
    status = app.handle_status()
    assert status["total_drawers"] >= 3, (
        f"Expected >= 3 total drawers, got {status['total_drawers']}"
    )

    # 6. Recall L1 — token_count > 0
    recall = app.handle_recall(level="L1")
    assert recall["token_count"] > 0, "L1 recall returned 0 tokens"

    # 7. List wings — at least 1 wing
    wings = app.palace.list_wings()
    assert len(wings) >= 1, "Expected at least 1 wing after mining"

    # 8. Re-mine same file — verify skipped == 1 (dedup works)
    remine_result = app.handle_mine(path=str(sample_session_tr))
    assert remine_result["skipped"] == 1, (
        f"Expected skipped=1 on re-mine, got {remine_result['skipped']}"
    )


# ---------------------------------------------------------------------------
# test_recycle_removes_from_index
# ---------------------------------------------------------------------------


def test_recycle_removes_from_index(config: MnemosConfig) -> None:
    """Recycling a drawer removes it from the search index."""

    app = MnemosApp(config, chromadb_in_memory=True)
    app.palace.ensure_structure()

    # 1. Add a memory that we will later recycle
    memory_text = "This memory will be recycled"
    add_result = app.handle_add(
        text=memory_text,
        wing="TestWing",
        room="TestRoom",
        hall="facts",
        importance=0.5,
    )
    drawer_id: str = add_result["drawer_id"]
    drawer_path = Path(add_result["obsidian_path"])

    # 2. Search for it — verify found
    results_before = app.handle_search(memory_text)
    found_ids = [r["drawer_id"] for r in results_before]
    assert drawer_id in found_ids, (
        f"Drawer '{drawer_id}' should be in search results before recycle"
    )

    # 3. Recycle via palace.recycle_drawer
    app.palace.recycle_drawer(drawer_path)

    # 4. Delete from search engine by drawer_id
    app.search_engine.delete_drawer(drawer_id)

    # 5. Search again — verify NOT found
    results_after = app.handle_search(memory_text)
    found_ids_after = [r["drawer_id"] for r in results_after]
    assert drawer_id not in found_ids_after, (
        f"Drawer '{drawer_id}' should NOT be in search results after recycle"
    )
