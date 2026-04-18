"""Tests for MnemosApp — core logic tested directly without MCP protocol."""
from __future__ import annotations

from pathlib import Path

import pytest

from mnemos.config import MnemosConfig
from mnemos.obsidian import write_drawer_file
from mnemos.server import MnemosApp


# ---------------------------------------------------------------------------
# test_app_status
# ---------------------------------------------------------------------------


def test_app_status(config: MnemosConfig) -> None:
    """ensure_structure then status returns total_drawers and vault_path."""
    app = MnemosApp(config, chromadb_in_memory=True)
    app.palace.ensure_structure()

    status = app.handle_status()

    assert "total_drawers" in status
    assert "vault_path" in status
    assert status["vault_path"] == config.vault_path
    assert isinstance(status["total_drawers"], int)
    assert status["total_drawers"] >= 0


# ---------------------------------------------------------------------------
# test_app_add_and_search
# ---------------------------------------------------------------------------


def test_app_add_and_search(config: MnemosConfig) -> None:
    """add memory, search for it, verify found."""
    app = MnemosApp(config, chromadb_in_memory=True)
    app.palace.ensure_structure()

    result = app.handle_add(
        text="Supabase RLS policy enforced on all tables",
        wing="ProcureTrack",
        room="Supabase",
        hall="decisions",
        importance=0.8,
    )

    assert "drawer_id" in result
    assert "obsidian_path" in result
    assert "message" in result

    # Search for the added content
    hits = app.handle_search(query="Supabase RLS policy", limit=5)

    assert len(hits) >= 1
    texts = [h["text"] for h in hits]
    assert any("Supabase" in t or "RLS" in t for t in texts)


# ---------------------------------------------------------------------------
# test_app_mine
# ---------------------------------------------------------------------------


def test_app_mine(config: MnemosConfig, sample_session_tr: Path) -> None:
    """mine sample_session_tr, verify drawers_created >= 1."""
    app = MnemosApp(config, chromadb_in_memory=True)
    app.palace.ensure_structure()

    result = app.handle_mine(path=str(sample_session_tr))

    assert "files_scanned" in result
    assert "drawers_created" in result
    assert "entities_found" in result
    assert "skipped" in result

    assert result["files_scanned"] >= 1
    assert result["drawers_created"] >= 1


# ---------------------------------------------------------------------------
# test_app_recall
# ---------------------------------------------------------------------------


def test_app_recall(config: MnemosConfig) -> None:
    """create wing, add first drawer (triggers lazy _wing.md), recall L1."""
    app = MnemosApp(config, chromadb_in_memory=True)
    app.palace.ensure_structure()

    app.palace.create_wing("ProcureTrack")
    app.palace.add_drawer(
        wing="ProcureTrack", room="intake", hall="facts",
        text="sample drawer body", source="test.md",
        importance=50, entities=[], language="en",
    )

    result = app.handle_recall(level="L1")

    assert "level" in result
    assert "content" in result
    assert "ProcureTrack" in result["content"]


# ---------------------------------------------------------------------------
# test_app_graph
# ---------------------------------------------------------------------------


def test_app_graph(config: MnemosConfig) -> None:
    """add triple, query graph, verify relation."""
    app = MnemosApp(config, chromadb_in_memory=True)
    app.palace.ensure_structure()

    app.graph.add_triple(
        subject="ProcureTrack",
        predicate="uses",
        obj="Supabase",
    )

    result = app.handle_graph(entity="ProcureTrack")

    assert "entity" in result
    assert "triples" in result
    assert result["entity"] == "ProcureTrack"

    predicates = [t["predicate"] for t in result["triples"]]
    assert "uses" in predicates


# ---------------------------------------------------------------------------
# test_app_timeline
# ---------------------------------------------------------------------------


def test_app_timeline(config: MnemosConfig) -> None:
    """add 2 triples with dates, verify timeline order."""
    app = MnemosApp(config, chromadb_in_memory=True)
    app.palace.ensure_structure()

    app.graph.add_triple(
        subject="ProcureTrack",
        predicate="launched",
        obj="MVP",
        valid_from="2026-01-01",
    )
    app.graph.add_triple(
        subject="ProcureTrack",
        predicate="deployed",
        obj="Production",
        valid_from="2026-03-15",
    )

    timeline = app.handle_timeline(entity="ProcureTrack")

    assert isinstance(timeline, list)
    assert len(timeline) >= 2

    # Verify ascending order by valid_from
    dates = [t["valid_from"] for t in timeline if t.get("valid_from")]
    assert dates == sorted(dates)


# ---------------------------------------------------------------------------
# test_app_wake_up
# ---------------------------------------------------------------------------


def test_app_wake_up(config: MnemosConfig) -> None:
    """create identity + wing, verify wake_up returns both."""
    app = MnemosApp(config, chromadb_in_memory=True)
    app.palace.ensure_structure()

    # Create identity file
    identity_file = config.identity_full_path / "L0-identity.md"
    write_drawer_file(
        identity_file,
        metadata={"type": "identity"},
        body="I am Mnemos. I remember everything.",
    )

    # Create a wing + first drawer (triggers lazy _wing.md)
    app.palace.create_wing("ProcureTrack")
    app.palace.add_drawer(
        wing="ProcureTrack", room="intake", hall="facts",
        text="sample drawer body", source="test.md",
        importance=50, entities=[], language="en",
    )

    result = app.handle_wake_up()

    assert "identity" in result
    assert "wings_summary" in result
    assert "token_count" in result

    assert "Mnemos" in result["identity"]
    assert "ProcureTrack" in result["wings_summary"]


# ---------------------------------------------------------------------------
# test_handle_mine_indexes_raw
# ---------------------------------------------------------------------------


def test_handle_mine_indexes_raw(config: MnemosConfig, sample_session_tr: Path) -> None:
    """Mining stores raw content in raw collection."""
    app = MnemosApp(config, chromadb_in_memory=True)
    app.palace.ensure_structure()

    result = app.handle_mine(path=str(sample_session_tr))
    assert result["drawers_created"] >= 0

    raw_count = app.search_engine._raw_collection.count()
    assert raw_count > 0


# ---------------------------------------------------------------------------
# test_handle_mine_skips_memory_md_index
# ---------------------------------------------------------------------------


def test_handle_mine_skips_memory_md_index(tmp_path: Path) -> None:
    """MEMORY.md files (Claude Code auto-memory index) must not be mined.

    They are pure wikilink indexes into their sibling files (user_profile.md,
    feedback_*.md, etc.); mining them as content produces duplicate-signal
    drawers pointing at already-indexed targets.
    """
    from mnemos.config import MnemosConfig

    cfg = MnemosConfig(vault_path=str(tmp_path))
    cfg.palace_dir.mkdir(parents=True, exist_ok=True)

    src = tmp_path / "memory-src"
    src.mkdir()
    # Claude-Code-shaped MEMORY.md (all wikilinks, almost no prose)
    (src / "MEMORY.md").write_text(
        "# Memory Index\n\n- [User profile](user_profile.md) — who I am\n"
        "- [Feedback](feedback_x.md) — preferences\n",
        encoding="utf-8",
    )
    # Real content file alongside
    (src / "user_profile.md").write_text(
        "---\nname: User Profile\ntype: user\n---\n\n"
        "Tugra Demirors works at GYP Energy. Prefers Turkish communication.",
        encoding="utf-8",
    )

    app = MnemosApp(cfg, chromadb_in_memory=True)
    app.palace.ensure_structure()
    result = app.handle_mine(path=str(src))

    # Exactly one file scanned (MEMORY.md skipped); user_profile.md processed.
    assert result["files_scanned"] == 1, result
    assert result["drawers_created"] >= 1, result

    # No drawer should carry MEMORY.md as its source.
    wings_dir = cfg.wings_dir
    sources = []
    for p in wings_dir.rglob("*.md"):
        if p.name.startswith("_"):
            continue
        for line in p.read_text(encoding="utf-8").splitlines()[:15]:
            if line.startswith("source:"):
                sources.append(line)
                break
    assert not any("MEMORY.md" in s for s in sources), sources


# ---------------------------------------------------------------------------
# test_handle_search_collection_param
# ---------------------------------------------------------------------------


def test_handle_search_collection_param(config: MnemosConfig, sample_session_tr: Path) -> None:
    """Search accepts collection parameter."""
    app = MnemosApp(config, chromadb_in_memory=True)
    app.palace.ensure_structure()

    app.handle_mine(path=str(sample_session_tr))

    results_raw = app.handle_search(query="test", collection="raw")
    assert isinstance(results_raw, list)

    results_mined = app.handle_search(query="test", collection="mined")
    assert isinstance(results_mined, list)


# ---------------------------------------------------------------------------
# test_handle_search_default_both
# ---------------------------------------------------------------------------


def test_handle_search_default_both(config: MnemosConfig, sample_session_tr: Path) -> None:
    """Default search uses both collections."""
    app = MnemosApp(config, chromadb_in_memory=True)
    app.palace.ensure_structure()

    app.handle_mine(path=str(sample_session_tr))

    results = app.handle_search(query="Supabase RLS")
    assert isinstance(results, list)
