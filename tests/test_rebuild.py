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


def test_resolve_sources_uses_config_mining_sources(tmp_path: Path):
    from mnemos.rebuild import _resolve_sources
    (tmp_path / "MyData").mkdir()
    cfg = MnemosConfig(vault_path=str(tmp_path))
    from mnemos.config import MiningSource
    cfg.mining_sources = [MiningSource(path="MyData", mode="session")]

    paths = _resolve_sources(cfg, explicit_path=None)
    assert len(paths) == 1
    assert paths[0].name == "MyData"


def test_resolve_sources_auto_discovers_sessions_topics(tmp_path: Path):
    from mnemos.rebuild import _resolve_sources
    (tmp_path / "Sessions").mkdir()
    (tmp_path / "Topics").mkdir()
    cfg = MnemosConfig(vault_path=str(tmp_path))

    paths = _resolve_sources(cfg, explicit_path=None)
    names = sorted(p.name for p in paths)
    assert names == ["Sessions", "Topics"]


def test_resolve_sources_explicit_path_wins(tmp_path: Path):
    from mnemos.rebuild import _resolve_sources
    (tmp_path / "Sessions").mkdir()
    (tmp_path / "Other").mkdir()
    cfg = MnemosConfig(vault_path=str(tmp_path))

    paths = _resolve_sources(cfg, explicit_path=str(tmp_path / "Other"))
    assert len(paths) == 1
    assert paths[0].name == "Other"


def test_resolve_sources_error_when_nothing(tmp_path: Path):
    from mnemos.rebuild import _resolve_sources, RebuildError
    cfg = MnemosConfig(vault_path=str(tmp_path))
    with pytest.raises(RebuildError) as exc:
        _resolve_sources(cfg, explicit_path=None)
    assert "mining_sources" in str(exc.value).lower() or "sessions" in str(exc.value).lower()


def test_build_plan_counts_source_files(tmp_path: Path):
    from mnemos.rebuild import build_plan
    sessions = tmp_path / "Sessions"
    sessions.mkdir()
    (sessions / "a.md").write_text("x", encoding="utf-8")
    (sessions / "b.md").write_text("y", encoding="utf-8")
    topics = tmp_path / "Topics"
    topics.mkdir()
    (topics / "c.md").write_text("z", encoding="utf-8")

    cfg = MnemosConfig(vault_path=str(tmp_path))

    plan = build_plan(cfg, explicit_path=None)
    assert plan["source_count"] == 3
    assert len(plan["sources"]) == 2
    assert "backup_path" in plan
    assert "existing_drawer_count" in plan


def test_format_plan_human_readable(tmp_path: Path):
    from mnemos.rebuild import build_plan, format_plan
    cfg = MnemosConfig(vault_path=str(tmp_path))
    (tmp_path / "Sessions").mkdir()
    (tmp_path / "Sessions" / "a.md").write_text("x", encoding="utf-8")

    plan = build_plan(cfg, explicit_path=None)
    text = format_plan(plan)
    assert "Sources:" in text
    assert "Backup:" in text
    assert "1 files" in text or "1 file" in text


def _seed_session(tmp_path: Path, name: str, body: str) -> Path:
    sessions = tmp_path / "Sessions"
    sessions.mkdir(exist_ok=True)
    src = sessions / name
    src.write_text(
        "---\nproject: Demo\n---\n" + body, encoding="utf-8",
    )
    return src


@pytest.mark.parametrize("backend_name", ["chromadb", "sqlite-vec"])
def test_rebuild_happy_path(tmp_path: Path, backend_name: str):
    from mnemos.rebuild import rebuild_vault
    cfg = MnemosConfig(vault_path=str(tmp_path), search_backend=backend_name)
    cfg.palace_dir.mkdir(parents=True, exist_ok=True)
    cfg.wings_dir.mkdir(parents=True, exist_ok=True)

    _seed_session(tmp_path, "2026-04-13-demo.md",
                  "We decided to use sqlite-vec. This is a discussion about the decision.")
    _seed_session(tmp_path, "2026-04-14-other.md",
                  "Another session about the testing strategy we chose.")

    result = rebuild_vault(cfg, explicit_path=None, yes=True, backup=True)

    assert result["rebuilt"] is True
    assert result["new_drawer_count"] > 0
    assert result["backup_path"]
    assert Path(result["backup_path"]).exists() is False  # no old wings to back up
    assert cfg.wings_dir.exists()


def test_rebuild_dry_run_does_nothing(tmp_path: Path):
    from mnemos.rebuild import rebuild_vault
    cfg = MnemosConfig(vault_path=str(tmp_path), search_backend="sqlite-vec")
    cfg.palace_dir.mkdir(parents=True, exist_ok=True)
    cfg.wings_dir.mkdir(parents=True, exist_ok=True)
    (cfg.wings_dir / "Existing").mkdir()

    _seed_session(tmp_path, "2026-04-13-demo.md", "Content")

    result = rebuild_vault(cfg, explicit_path=None, yes=True, backup=True, dry_run=True)

    assert result["dry_run"] is True
    assert (cfg.wings_dir / "Existing").exists()  # not touched


def test_rebuild_rollback_on_zero_drawers(tmp_path: Path):
    """If re-mine produces zero drawers, backup must be restored."""
    from mnemos.rebuild import rebuild_vault, RebuildError
    cfg = MnemosConfig(vault_path=str(tmp_path), search_backend="sqlite-vec")
    cfg.palace_dir.mkdir(parents=True, exist_ok=True)
    cfg.wings_dir.mkdir(parents=True, exist_ok=True)
    (cfg.wings_dir / "OldWing").mkdir()
    (cfg.wings_dir / "OldWing" / "marker.md").write_text("old", encoding="utf-8")

    # Sessions exists but has no .md files -> miner produces 0 drawers
    (tmp_path / "Sessions").mkdir()

    with pytest.raises(RebuildError) as exc:
        rebuild_vault(cfg, explicit_path=None, yes=True, backup=True)
    assert "no drawers" in str(exc.value).lower() or "rollback" in str(exc.value).lower()

    assert (cfg.wings_dir / "OldWing" / "marker.md").exists()

    # Index must also be restored (empty here; no drawers ever indexed), and
    # the backend must be re-openable after rollback.
    backend = SearchEngine(cfg)
    try:
        stats = backend.get_stats()
        assert stats["total_drawers"] == 0
    finally:
        backend.close()


def test_rebuild_lock_prevents_concurrent(tmp_path: Path):
    from mnemos.rebuild import rebuild_vault, RebuildError
    cfg = MnemosConfig(vault_path=str(tmp_path), search_backend="sqlite-vec")
    cfg.palace_dir.mkdir(parents=True, exist_ok=True)
    cfg.wings_dir.mkdir(parents=True, exist_ok=True)
    _seed_session(tmp_path, "2026-04-13-x.md", "content")

    lock_file = cfg.palace_dir / ".rebuild.lock"
    lock_file.touch()

    from filelock import FileLock
    lock = FileLock(str(lock_file) + ".flock", timeout=0.1)
    lock.acquire()
    try:
        with pytest.raises(RebuildError) as exc:
            rebuild_vault(cfg, explicit_path=None, yes=True, backup=True)
        assert "lock" in str(exc.value).lower() or "already in progress" in str(exc.value).lower()
    finally:
        lock.release()


def test_rebuild_succeeds_past_stale_lock_file(tmp_path: Path):
    """A lock file on disk that no one holds must not block a new rebuild."""
    from mnemos.rebuild import rebuild_vault
    cfg = MnemosConfig(vault_path=str(tmp_path), search_backend="sqlite-vec")
    cfg.palace_dir.mkdir(parents=True, exist_ok=True)
    cfg.wings_dir.mkdir(parents=True, exist_ok=True)
    _seed_session(tmp_path, "2026-04-13-demo.md", "We picked sqlite-vec.")

    # Simulate a crashed prior rebuild: lock file exists but no process holds it.
    stale_lock = cfg.palace_dir / ".rebuild.lock.flock"
    stale_lock.touch()

    result = rebuild_vault(cfg, explicit_path=None, yes=True, backup=True)
    assert result["rebuilt"] is True


def test_build_plan_result_is_json_serializable(tmp_path: Path):
    """CLI prints the plan via json.dumps; all values must be JSON-safe."""
    import json
    from mnemos.rebuild import build_plan
    (tmp_path / "Sessions").mkdir()
    (tmp_path / "Sessions" / "a.md").write_text("x", encoding="utf-8")
    cfg = MnemosConfig(vault_path=str(tmp_path))

    plan = build_plan(cfg, explicit_path=None)
    # Must not raise TypeError on Path objects etc.
    payload = json.dumps({"dry_run": True, "plan": plan}, ensure_ascii=False)
    assert "Sessions" in payload
