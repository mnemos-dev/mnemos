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
    MigrateError,
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


def test_format_estimate_uses_seconds_below_one_minute() -> None:
    """Tiny vaults estimate in seconds instead of `~0–0 minutes`."""
    plan = MigrationPlan(
        from_backend="chromadb",
        to_backend="sqlite-vec",
        current_drawers=5,
        source_files=1,
        estimate_min_seconds=1.6,
        estimate_max_seconds=3.0,
    )
    assert plan.format_estimate() == "~2–3 seconds"


def test_format_estimate_floors_min_at_one_second() -> None:
    """Sub-second windows still render ≥1 second so user sees a real number."""
    plan = MigrationPlan(
        from_backend="chromadb",
        to_backend="sqlite-vec",
        current_drawers=1,
        source_files=1,
        estimate_min_seconds=0.32,
        estimate_max_seconds=0.60,
    )
    assert plan.format_estimate() == "~1–1 second"


def test_format_estimate_switches_to_minutes_when_max_reaches_one_minute() -> None:
    """Once the upper bound crosses 60s the unit flips to minutes."""
    plan = MigrationPlan(
        from_backend="chromadb",
        to_backend="sqlite-vec",
        current_drawers=140,
        source_files=20,
        estimate_min_seconds=45,
        estimate_max_seconds=84,
    )
    result = plan.format_estimate()
    assert "minute" in result
    assert "second" not in result


def test_format_estimate_large_vault_uses_minutes_plural() -> None:
    """Large estimates use `minutes` with the correct minute range."""
    plan = MigrationPlan(
        from_backend="chromadb",
        to_backend="sqlite-vec",
        current_drawers=8000,
        source_files=100,
        estimate_min_seconds=2560,
        estimate_max_seconds=4800,
    )
    assert plan.format_estimate() == "~43–80 minutes"


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


# ---------------------------------------------------------------------------
# Rollback + migration lock
# ---------------------------------------------------------------------------


def test_migrate_rolls_back_on_rebuild_failure(tmp_path: Path, monkeypatch) -> None:
    """If rebuild blows up, yaml and storage must return to the old backend."""
    from mnemos import migrate as migrate_mod

    vault = _seed_vault(tmp_path, backend="chromadb")
    cfg = load_config(str(vault))
    assert cfg.chromadb_full_path.exists()

    def _boom(_vault_path: str) -> int:
        raise RuntimeError("simulated rebuild failure")

    monkeypatch.setattr(migrate_mod, "_rebuild_with_new_backend", _boom)

    with pytest.raises(MigrateError, match="rolled back"):
        migrate(cfg, new_backend="sqlite-vec")

    # yaml reverted to chromadb (parsed — yaml.safe_dump may reformat list indent)
    yaml_after = yaml.safe_load((vault / "mnemos.yaml").read_text(encoding="utf-8"))
    assert yaml_after["search_backend"] == "chromadb"
    # ChromaDB storage restored from backup — still the live backend
    assert cfg.chromadb_full_path.exists()
    # No orphaned backup sitting next to restored storage
    palace = cfg.palace_dir
    assert not any(p.name.startswith(".chroma.bak") for p in palace.iterdir())
    # Partial sqlite-vec storage cleaned up
    assert not (palace / "search.sqlite3").exists()


def test_migrate_rollback_restores_mine_log(tmp_path: Path, monkeypatch) -> None:
    """Rollback puts mine_log back where it was so the next run doesn't rescan."""
    from mnemos import migrate as migrate_mod

    vault = _seed_vault(tmp_path, backend="chromadb")
    cfg = load_config(str(vault))
    mine_log = cfg.mine_log_full_path
    assert mine_log.exists(), "seed vault must have mined content"
    mine_log_before = mine_log.read_text(encoding="utf-8")

    monkeypatch.setattr(
        migrate_mod,
        "_rebuild_with_new_backend",
        lambda _p: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    with pytest.raises(MigrateError):
        migrate(cfg, new_backend="sqlite-vec")

    assert mine_log.exists()
    assert mine_log.read_text(encoding="utf-8") == mine_log_before


def test_migrate_lock_blocks_concurrent_migration(tmp_path: Path) -> None:
    """A second migrate attempt while the lock is held raises MigrateError."""
    from filelock import FileLock

    vault = _seed_vault(tmp_path, backend="chromadb")
    cfg = load_config(str(vault))
    cfg.palace_dir.mkdir(parents=True, exist_ok=True)

    competitor = FileLock(str(cfg.palace_dir / ".migrate.lock.flock"))
    competitor.acquire(timeout=1)
    try:
        with pytest.raises(MigrateError, match="already running"):
            migrate(cfg, new_backend="sqlite-vec")
    finally:
        competitor.release()

    # After release the next migrate can acquire the lock normally (no stale file block)
    result = migrate(cfg, new_backend="sqlite-vec")
    assert result.status == "migrated"
