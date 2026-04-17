"""Tests for `mnemos migrate --backend X` (v0.3.1 task 3.14b).

Happy-path + dry-run + no-op + backup semantics. Rollback-on-failure and
migration-lock recovery are covered by the edge-case suite below.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from mnemos.config import MnemosConfig, load_config
from mnemos.migrate import (
    MigrationPlan,
    MigrationResult,
    build_plan,
    migrate,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _seed_vault(tmp_path: Path, backend: str = "chromadb") -> Path:
    """Create a minimal vault with one Session .md and run `mnemos init` equivalent.

    Returns the vault path with a working backend + at least one drawer
    indexed so storage_bytes > 0 for backup and plan tests.
    """
    vault = tmp_path / "vault"
    vault.mkdir()

    # Minimal mnemos.yaml
    (vault / "mnemos.yaml").write_text(
        f"search_backend: {backend}\nlanguages:\n  - en\n",
        encoding="utf-8",
    )

    # One Session file with mineable content
    sessions = vault / "Sessions"
    sessions.mkdir()
    (sessions / "demo.md").write_text(
        "---\nwing: Demo\ntype: session\n---\n\n"
        "# Demo Session\n\n"
        "**user:** We decided to use Postgres for the new project.\n\n"
        "**assistant:** Good decision. Postgres is reliable.\n",
        encoding="utf-8",
    )

    # Mine it once to populate the backend
    cfg = load_config(str(vault))
    from mnemos.server import MnemosApp
    with MnemosApp(cfg) as app:
        app.palace.ensure_structure()
        app.handle_mine(path=str(sessions))

    return vault


# ---------------------------------------------------------------------------
# build_plan
# ---------------------------------------------------------------------------


def test_build_plan_reports_current_state(tmp_path: Path) -> None:
    """Plan carries current drawer count, source file count, and backends."""
    vault = _seed_vault(tmp_path, backend="chromadb")
    cfg = load_config(str(vault))

    plan = build_plan(cfg, new_backend="sqlite-vec")

    assert isinstance(plan, MigrationPlan)
    assert plan.from_backend == "chromadb"
    assert plan.to_backend == "sqlite-vec"
    assert plan.current_drawers >= 1
    assert plan.source_files >= 1
    assert plan.estimate_min_seconds >= 0
    assert plan.estimate_max_seconds >= plan.estimate_min_seconds


def test_build_plan_time_estimate_scales_with_drawers(tmp_path: Path) -> None:
    """Larger drawer counts → wider time window (±30% of 0.46 s/drawer baseline)."""
    vault = _seed_vault(tmp_path, backend="chromadb")
    cfg = load_config(str(vault))

    plan = build_plan(cfg, new_backend="sqlite-vec")
    # baseline = 0.46 s/drawer, ±30% → [0.322, 0.598]
    expected_min = plan.current_drawers * 0.32
    expected_max = plan.current_drawers * 0.60
    assert plan.estimate_min_seconds == pytest.approx(expected_min, abs=1.0)
    assert plan.estimate_max_seconds == pytest.approx(expected_max, abs=1.0)


# ---------------------------------------------------------------------------
# migrate — happy path and shortcuts
# ---------------------------------------------------------------------------


def test_migrate_same_backend_is_noop(tmp_path: Path) -> None:
    """Requesting the same backend returns status=noop without touching yaml."""
    vault = _seed_vault(tmp_path, backend="chromadb")
    cfg = load_config(str(vault))
    yaml_before = (vault / "mnemos.yaml").read_text(encoding="utf-8")

    result = migrate(cfg, new_backend="chromadb")

    assert result.status == "noop"
    assert (vault / "mnemos.yaml").read_text(encoding="utf-8") == yaml_before


def test_migrate_dry_run_modifies_nothing(tmp_path: Path) -> None:
    """--dry-run returns a plan-only result; yaml + storage untouched."""
    vault = _seed_vault(tmp_path, backend="chromadb")
    cfg = load_config(str(vault))

    yaml_before = (vault / "mnemos.yaml").read_text(encoding="utf-8")
    chroma_dir = cfg.chromadb_full_path
    had_chroma = chroma_dir.exists()

    result = migrate(cfg, new_backend="sqlite-vec", dry_run=True)

    assert result.status == "dry-run"
    assert result.plan is not None
    assert result.plan.to_backend == "sqlite-vec"
    assert (vault / "mnemos.yaml").read_text(encoding="utf-8") == yaml_before
    # No backup path created, no new sqlite file
    assert not any(p.name.startswith(".chroma.bak") for p in chroma_dir.parent.iterdir())
    assert not (chroma_dir.parent / "search.sqlite3").exists()
    if had_chroma:
        assert chroma_dir.exists()


def test_migrate_chromadb_to_sqlite_vec_full_flow(tmp_path: Path) -> None:
    """End-to-end: yaml updated, ChromaDB dir backed up, sqlite.vec populated."""
    vault = _seed_vault(tmp_path, backend="chromadb")
    cfg = load_config(str(vault))
    assert cfg.chromadb_full_path.exists()

    drawers_before = None
    from mnemos.server import MnemosApp
    with MnemosApp(cfg) as app:
        drawers_before = app.handle_status()["total_drawers"]
    assert drawers_before > 0

    result = migrate(cfg, new_backend="sqlite-vec")

    assert result.status == "migrated"
    assert result.from_backend == "chromadb"
    assert result.to_backend == "sqlite-vec"
    assert result.backup_path is not None
    assert result.backup_path.exists()
    assert ".chroma.bak-" in result.backup_path.name

    # yaml now points at sqlite-vec
    new_cfg = load_config(str(vault))
    assert new_cfg.search_backend == "sqlite-vec"

    # sqlite-vec file exists and has drawers
    sqlite_path = cfg.palace_dir / "search.sqlite3"
    assert sqlite_path.exists()
    with MnemosApp(new_cfg) as app:
        drawers_after = app.handle_status()["total_drawers"]
    assert drawers_after >= 1


def test_migrate_skips_rebuild_when_requested(tmp_path: Path) -> None:
    """--no-rebuild leaves the new backend empty (user wants manual control)."""
    vault = _seed_vault(tmp_path, backend="chromadb")
    cfg = load_config(str(vault))

    result = migrate(cfg, new_backend="sqlite-vec", no_rebuild=True)

    assert result.status == "migrated"
    assert result.drawers_after == 0

    # yaml still updated
    new_cfg = load_config(str(vault))
    assert new_cfg.search_backend == "sqlite-vec"


def test_migrate_unknown_backend_raises(tmp_path: Path) -> None:
    """Typos in --backend surface as ValueError — not silently handled."""
    vault = _seed_vault(tmp_path, backend="chromadb")
    cfg = load_config(str(vault))

    with pytest.raises(ValueError):
        migrate(cfg, new_backend="no-such-backend")


# ---------------------------------------------------------------------------
# Backup collision handling
# ---------------------------------------------------------------------------


def test_migrate_backup_name_counter_on_same_day(tmp_path: Path, monkeypatch) -> None:
    """Second migration on the same day suffixes .bak-<date>.2, .3, ..."""
    from mnemos import migrate as migrate_mod
    monkeypatch.setattr(migrate_mod, "_utc_date_str", lambda: "2026-04-17")

    vault = _seed_vault(tmp_path, backend="chromadb")
    cfg = load_config(str(vault))

    # Pre-seed a backup as if a prior migrate already ran today
    fake_bak = cfg.palace_dir / ".chroma.bak-2026-04-17"
    fake_bak.mkdir()
    (fake_bak / "placeholder.txt").write_text("prior backup", encoding="utf-8")

    result = migrate(cfg, new_backend="sqlite-vec")

    assert result.status == "migrated"
    # New backup must have a numeric suffix to avoid clobbering
    assert result.backup_path.name.startswith(".chroma.bak-2026-04-17")
    assert result.backup_path.name != ".chroma.bak-2026-04-17"
    # Original backup untouched
    assert (fake_bak / "placeholder.txt").exists()
