"""`mnemos migrate --backend X` — switch vector backends safely.

Two backends ship in mnemos: chromadb (default, mature) and sqlite-vec
(single-file, robust on Windows + Python 3.14). A 2026-04-17 parity
benchmark showed they produce identical recall on LongMemEval. This
module lets a user switch between them without editing mnemos.yaml by
hand or losing data — the vault's .md files are the source of truth,
so a fresh rebuild reproduces every drawer.

Flow:
  1. Build a plan: count current drawers, source .md files, estimated
     rebuild time.
  2. Back up the old backend's storage (directory or file) with a
     date-stamped suffix — never overwrite an existing backup.
  3. Update search_backend in mnemos.yaml.
  4. Clear mine_log so the rebuild re-scans everything.
  5. Open a fresh MnemosApp with the new backend and mine the vault.
  6. Return a summary with drawers before/after and backup location.

Edge cases like rollback-on-failure and migration-lock recovery are
deferred to follow-up passes — this module establishes the happy path
plus no-op/dry-run/same-backend shortcuts.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from mnemos.config import MnemosConfig, load_config


# Source directories scanned for rebuild. Keep in sync with ROADMAP/spec:
# curated markdown lives under Sessions/ + Topics/ + memory/.
_DEFAULT_SOURCE_DIRS = ("Sessions", "Topics", "memory")

# Time estimate — from 2026-04-17 LongMemEval parity benchmark
# (8027 drawers / 62 min ≈ 0.46 s/drawer). ±30% margin for the
# min/max window users see in dry-run / plan output.
_SECONDS_PER_DRAWER = 0.46
_ESTIMATE_LOWER = 0.70  # 0.46 × 0.70 ≈ 0.32 s/drawer
_ESTIMATE_UPPER = 1.30  # 0.46 × 1.30 ≈ 0.60 s/drawer

_KNOWN_BACKENDS = ("chromadb", "sqlite-vec")


def _utc_date_str() -> str:
    """Monkeypatch seam for deterministic backup naming in tests."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@dataclass
class MigrationPlan:
    """What would happen if we migrated now — preview for --dry-run."""

    from_backend: str
    to_backend: str
    current_drawers: int
    source_files: int
    estimate_min_seconds: float
    estimate_max_seconds: float
    source_dirs: list[str] = field(default_factory=list)

    def estimate_minutes_range(self) -> tuple[int, int]:
        lo = max(0, int(round(self.estimate_min_seconds / 60)))
        hi = max(lo, int(round(self.estimate_max_seconds / 60)))
        return lo, hi


@dataclass
class MigrationResult:
    """Outcome of :func:`migrate`."""

    status: str  # "noop" | "dry-run" | "migrated"
    from_backend: str
    to_backend: str
    drawers_before: int = 0
    drawers_after: int = 0
    backup_path: Optional[Path] = None
    plan: Optional[MigrationPlan] = None
    source_files: int = 0


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


def _count_source_files(cfg: MnemosConfig) -> tuple[int, list[str]]:
    """Count .md files in the canonical source directories that exist."""
    vault = Path(cfg.vault_path)
    total = 0
    present: list[str] = []
    for name in _DEFAULT_SOURCE_DIRS:
        d = vault / name
        if not d.is_dir():
            continue
        count = sum(1 for _ in d.rglob("*.md"))
        total += count
        if count > 0:
            present.append(name)
    return total, present


def _current_drawer_count(cfg: MnemosConfig) -> int:
    """Ask the current backend how many drawers are indexed."""
    from mnemos.server import MnemosApp
    try:
        with MnemosApp(cfg) as app:
            return int(app.handle_status().get("total_drawers") or 0)
    except Exception:
        # A corrupt current backend shouldn't block a migration plan
        return 0


def build_plan(cfg: MnemosConfig, new_backend: str) -> MigrationPlan:
    """Collect counts and time estimate without touching any files."""
    _require_known_backend(new_backend)

    drawers = _current_drawer_count(cfg)
    source_files, source_dirs = _count_source_files(cfg)

    # Rebuild cost scales with current drawer count (fresh mine writes the
    # same number back). Raw source file count is informational — the
    # miner may emit multiple drawers per file.
    est_mid = drawers * _SECONDS_PER_DRAWER
    return MigrationPlan(
        from_backend=cfg.search_backend,
        to_backend=new_backend,
        current_drawers=drawers,
        source_files=source_files,
        estimate_min_seconds=est_mid * _ESTIMATE_LOWER,
        estimate_max_seconds=est_mid * _ESTIMATE_UPPER,
        source_dirs=source_dirs,
    )


# ---------------------------------------------------------------------------
# migrate()
# ---------------------------------------------------------------------------


def migrate(
    cfg: MnemosConfig,
    new_backend: str,
    dry_run: bool = False,
    no_rebuild: bool = False,
) -> MigrationResult:
    """Move *cfg*'s vault from its current backend to *new_backend*.

    Args:
        cfg: Loaded config for the vault whose backend we're changing.
        new_backend: Target backend name — ``"chromadb"`` or ``"sqlite-vec"``.
        dry_run: If True, return a plan-only result without changing anything.
        no_rebuild: If True, update yaml + back up old storage but skip the
            full rebuild. Useful when the user wants to re-mine manually or
            in chunks.

    Returns:
        :class:`MigrationResult` describing what happened.
    """
    _require_known_backend(new_backend)

    if new_backend == cfg.search_backend:
        return MigrationResult(
            status="noop",
            from_backend=cfg.search_backend,
            to_backend=new_backend,
        )

    plan = build_plan(cfg, new_backend)

    if dry_run:
        return MigrationResult(
            status="dry-run",
            from_backend=cfg.search_backend,
            to_backend=new_backend,
            drawers_before=plan.current_drawers,
            plan=plan,
            source_files=plan.source_files,
        )

    # Close any live backend before moving its storage — Windows refuses
    # to rename open directories.
    backup_path = _backup_old_storage(cfg)
    _write_backend_in_yaml(cfg.vault_path, new_backend)
    _clear_mine_log(cfg)

    drawers_after = 0
    if not no_rebuild:
        drawers_after = _rebuild_with_new_backend(cfg.vault_path)

    return MigrationResult(
        status="migrated",
        from_backend=cfg.search_backend,
        to_backend=new_backend,
        drawers_before=plan.current_drawers,
        drawers_after=drawers_after,
        backup_path=backup_path,
        plan=plan,
        source_files=plan.source_files,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_known_backend(name: str) -> None:
    if name not in _KNOWN_BACKENDS:
        raise ValueError(
            f"Unknown backend: {name!r}. Valid: {', '.join(_KNOWN_BACKENDS)}"
        )


def _backup_old_storage(cfg: MnemosConfig) -> Optional[Path]:
    """Rename the current backend's storage to a dated backup directory.

    Returns the backup Path or None if nothing existed to back up.
    """
    old_backend = cfg.search_backend
    palace = cfg.palace_dir

    if old_backend == "chromadb":
        src = cfg.chromadb_full_path
        target_stem = f".chroma.bak-{_utc_date_str()}"
    elif old_backend == "sqlite-vec":
        src = palace / "search.sqlite3"
        target_stem = f"search.sqlite3.bak-{_utc_date_str()}"
    else:  # pragma: no cover — validated upstream
        raise ValueError(f"Unknown current backend: {old_backend!r}")

    if not src.exists():
        return None

    target = palace / target_stem
    # Collision-safe: if this date's backup already exists, append a counter.
    if target.exists():
        counter = 2
        while (palace / f"{target_stem}.{counter}").exists():
            counter += 1
        target = palace / f"{target_stem}.{counter}"

    src.rename(target)
    return target


def _write_backend_in_yaml(vault_path: str, new_backend: str) -> None:
    """Set ``search_backend`` in the vault's mnemos.yaml, preserving other keys."""
    yaml_path = Path(vault_path) / "mnemos.yaml"
    if yaml_path.exists():
        with yaml_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    else:
        data = {}
    data["search_backend"] = new_backend
    with yaml_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False)


def _clear_mine_log(cfg: MnemosConfig) -> None:
    """Remove mine_log so the rebuild re-scans every .md file."""
    mine_log = cfg.mine_log_full_path
    if mine_log.exists():
        mine_log.unlink()


def _rebuild_with_new_backend(vault_path: str) -> int:
    """Mine every source directory into the freshly-switched backend.

    Returns total drawers in the new index afterwards.
    """
    # Reload config so MnemosApp picks up the new search_backend.
    new_cfg = load_config(vault_path)
    from mnemos.server import MnemosApp

    total = 0
    with MnemosApp(new_cfg) as app:
        app.palace.ensure_structure()
        for name in _DEFAULT_SOURCE_DIRS:
            d = Path(vault_path) / name
            if not d.is_dir():
                continue
            app.handle_mine(path=str(d))
        total = int(app.handle_status().get("total_drawers") or 0)
    return total
