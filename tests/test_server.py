"""Tests for MnemosApp — core logic tested directly without MCP protocol.

v1.0: ``MnemosApp`` no longer owns the mining/drawer paradigm — ``handle_add``,
``handle_mine``, ``palace``, ``miner``, and ``on_vault_change`` were removed
when ``mnemos.miner`` and ``mnemos.palace`` were deleted in Task 3. The
remaining surface is read-only (search/status/recall/graph/timeline/wake_up),
so these tests seed the index / wings / graph through their canonical APIs
and exercise the App-level handlers.

Tests for the deleted handlers (``test_app_add_and_search``, ``test_app_mine``,
``test_handle_mine_indexes_raw``, ``test_handle_mine_skips_memory_md_index``,
``test_handle_search_collection_param``, ``test_handle_search_default_both``)
were removed; they are not coming back on the Sessions paradigm.
"""
from __future__ import annotations

from pathlib import Path

from mnemos.config import MnemosConfig
from mnemos.obsidian import write_drawer_file
from mnemos.server import MnemosApp


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _seed_wing(config: MnemosConfig, wing: str, body: str = "Wing summary body.") -> None:
    """Write ``wings/<wing>/_wing.md`` directly — replaces the old
    ``Palace.create_wing`` + ``Palace.add_drawer`` seeding pattern.
    """
    wing_dir = config.wings_dir / wing
    wing_dir.mkdir(parents=True, exist_ok=True)
    write_drawer_file(
        wing_dir / "_wing.md",
        metadata={"type": "wing-summary", "wing": wing},
        body=body,
    )


# ---------------------------------------------------------------------------
# test_app_status
# ---------------------------------------------------------------------------


def test_app_status(config: MnemosConfig) -> None:
    """status returns total_drawers and vault_path on a fresh app."""
    app = MnemosApp(config, chromadb_in_memory=True)

    status = app.handle_status()

    assert "total_drawers" in status
    assert "vault_path" in status
    assert status["vault_path"] == config.vault_path
    assert isinstance(status["total_drawers"], int)
    assert status["total_drawers"] >= 0
    # v1.0: backend metadata block is part of the status contract
    assert "backend" in status
    assert status["backend"]["name"] == config.search_backend


# ---------------------------------------------------------------------------
# test_app_status_lists_wings_from_disk
# ---------------------------------------------------------------------------


def test_app_status_lists_wings_from_disk(config: MnemosConfig) -> None:
    """status reads wings_dir directly — no Palace required."""
    _seed_wing(config, "ProcureTrack")
    _seed_wing(config, "Mnemos")

    app = MnemosApp(config, chromadb_in_memory=True)
    status = app.handle_status()

    assert sorted(status["wings"]) == ["Mnemos", "ProcureTrack"]


# ---------------------------------------------------------------------------
# test_app_recall
# ---------------------------------------------------------------------------


def test_app_recall(config: MnemosConfig) -> None:
    """v1.0: L0 recall surfaces Identity Layer content via MemoryStack.

    The drawer paradigm (L1 wings, L2 rooms) was retired in the
    narrative-first pivot — see ``test_recall_l1_returns_deprecated_marker``
    in ``test_mcp_v1.py`` for the deprecation contract.
    """
    from pathlib import Path

    identity_dir = Path(config.vault_path) / "_identity"
    identity_dir.mkdir(parents=True, exist_ok=True)
    (identity_dir / "L0-identity.md").write_text(
        "# User Identity\n\nWorking on ProcureTrack.\n",
        encoding="utf-8",
    )

    app = MnemosApp(config, chromadb_in_memory=True)

    result = app.handle_recall(level="L0")

    assert "identity" in result
    assert "ProcureTrack" in result["identity"]


# ---------------------------------------------------------------------------
# test_app_graph
# ---------------------------------------------------------------------------


def test_app_graph(config: MnemosConfig) -> None:
    """add triple, query graph, verify relation."""
    app = MnemosApp(config, chromadb_in_memory=True)

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
    """v1.0: wake_up returns the Identity Layer body only.

    The wings_summary key was removed when the drawer paradigm was retired
    in the narrative-first pivot. Identity now lives at
    ``<vault>/_identity/L0-identity.md`` (vault root, not palace_root).
    """
    from pathlib import Path

    identity_dir = Path(config.vault_path) / "_identity"
    identity_dir.mkdir(parents=True, exist_ok=True)
    (identity_dir / "L0-identity.md").write_text(
        "# User Identity\n\nI am Mnemos. I remember everything.\n",
        encoding="utf-8",
    )

    app = MnemosApp(config, chromadb_in_memory=True)
    result = app.handle_wake_up()

    assert "identity" in result
    assert "token_count" in result
    assert "Mnemos" in result["identity"]
