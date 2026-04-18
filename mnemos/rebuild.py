"""Atomic rebuild of the mnemos palace.

See docs/specs/2026-04-18-v0.3.2-palace-hygiene-design.md §4.
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from mnemos.config import MnemosConfig


class RebuildError(Exception):
    """Raised when rebuild cannot proceed or must abort."""


def _resolve_sources(
    cfg: MnemosConfig, explicit_path: str | None
) -> list[Path]:
    """Resolve the list of source directories to mine during rebuild.

    Order:
      1. *explicit_path* wins if given.
      2. ``cfg.mining_sources`` yaml entries if non-empty.
      3. Auto-discover ``<vault>/Sessions`` and ``<vault>/Topics`` if either
         exists.
      4. Raise :class:`RebuildError`.
    """
    vault_path = Path(cfg.vault_path)

    if explicit_path:
        p = Path(explicit_path)
        if not p.is_absolute():
            p = vault_path / p
        return [p]

    if cfg.mining_sources:
        out: list[Path] = []
        for src in cfg.mining_sources:
            p = Path(src.path)
            if not p.is_absolute():
                p = vault_path / p
            out.append(p)
        return out

    auto_paths: list[Path] = []
    for name in ("Sessions", "Topics"):
        candidate = vault_path / name
        if candidate.exists() and candidate.is_dir():
            auto_paths.append(candidate)
    if auto_paths:
        return auto_paths

    raise RebuildError(
        "No mining sources configured. Either:\n"
        "  - add `mining_sources` to mnemos.yaml, or\n"
        "  - pass an explicit path to `mnemos mine --rebuild <path>`, or\n"
        "  - create `Sessions/` or `Topics/` under the vault"
    )


def build_plan(cfg: MnemosConfig, explicit_path: str | None) -> dict:
    """Gather rebuild metadata without performing any action."""
    sources = _resolve_sources(cfg, explicit_path)
    per_source: list[dict] = []
    total_files = 0
    for src in sources:
        if src.is_file():
            files = [src]
        elif src.is_dir():
            files = list(src.rglob("*.md"))
        else:
            files = []
        per_source.append({"path": str(src), "file_count": len(files)})
        total_files += len(files)

    existing_drawers = 0
    if cfg.wings_dir.exists():
        existing_drawers = sum(
            1 for p in cfg.wings_dir.rglob("*.md")
            if not p.name.startswith("_")
        )

    ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    return {
        "sources": per_source,
        "source_count": total_files,
        "existing_drawer_count": existing_drawers,
        "backup_path": str(cfg.recycled_full_path / f"wings-{ts}"),
        "timestamp": ts,
    }


def format_plan(plan: dict) -> str:
    lines = ["Rebuild plan:"]
    src_parts = [
        f"{Path(s['path']).name} ({s['file_count']} files)"
        for s in plan["sources"]
    ]
    lines.append(f"  Sources: {', '.join(src_parts)} = {plan['source_count']} files")
    lines.append(f"  Current drawers: {plan['existing_drawer_count']}")
    lines.append(f"  Backup: {plan['backup_path']}")
    return "\n".join(lines)


def rebuild_vault(
    cfg: MnemosConfig,
    explicit_path: str | None = None,
    *,
    dry_run: bool = False,
    yes: bool = False,
    backup: bool = True,
) -> dict:
    """Atomic rebuild of the mnemos palace.

    Phases: resolve → plan → (dry-run?) → confirm → lock → backup wings +
    index + graph → drop+reinit → graph.reset → re-mine → verify → return.
    Rolls back wings/index/graph from backup on any failure.
    """
    from filelock import FileLock, Timeout

    from mnemos.graph import KnowledgeGraph
    from mnemos.palace import Palace
    from mnemos.search import SearchEngine

    plan = build_plan(cfg, explicit_path)
    if dry_run:
        print(format_plan(plan))
        return {"dry_run": True, "plan": plan}

    if not yes:
        print(format_plan(plan))
        reply = input("Proceed? [y/N] ").strip().lower()
        if reply not in {"y", "yes"}:
            raise RebuildError("Rebuild aborted by user")

    cfg.palace_dir.mkdir(parents=True, exist_ok=True)
    lock_path = cfg.palace_dir / ".rebuild.lock.flock"
    lock = FileLock(str(lock_path), timeout=1)

    try:
        lock.acquire()
    except Timeout:
        raise RebuildError(
            "Rebuild lock is already held — another rebuild is in progress"
        )

    backup_path: Path | None = None
    index_backup: Path | None = None
    graph_backup: Path | None = None
    storage_path: Path | None = None

    try:
        palace = Palace(cfg)
        if backup and cfg.wings_dir.exists() and any(cfg.wings_dir.iterdir()):
            backup_path = palace.backup_wings(timestamp=plan["timestamp"])

        backend = SearchEngine(cfg)
        storage_path = backend.storage_path()
        ts = plan["timestamp"]
        if backup and storage_path and storage_path.exists():
            if storage_path.is_file():
                index_backup = storage_path.with_name(
                    storage_path.name + f".bak-{ts}"
                )
                shutil.copy2(storage_path, index_backup)
            else:
                index_backup = storage_path.with_name(
                    storage_path.name + f".bak-{ts}"
                )
                shutil.copytree(storage_path, index_backup)

        if backup and cfg.graph_full_path.exists():
            graph_backup = cfg.graph_full_path.with_name(
                cfg.graph_full_path.name + f".bak-{ts}"
            )
            shutil.copy2(cfg.graph_full_path, graph_backup)

        backend.drop_and_reinit()
        backend.close()

        graph = KnowledgeGraph(cfg.graph_full_path)
        graph.reset()
        try:
            graph._conn.close()
        except Exception:
            pass

        from mnemos.server import MnemosApp
        cfg.wings_dir.mkdir(parents=True, exist_ok=True)
        new_drawer_count = 0
        with MnemosApp(cfg) as app:
            app._mine_log = {}
            app._save_mine_log()
            sources = _resolve_sources(cfg, explicit_path)
            for src in sources:
                if not src.exists():
                    print(f"Source not found, skipping: {src}")
                    continue
                result = app.handle_mine(path=str(src), use_llm=cfg.use_llm)
                new_drawer_count += result.get("drawers_created", 0)

        if new_drawer_count == 0:
            raise RebuildError(
                "Rebuild produced no drawers — rolling back"
            )
        if plan["existing_drawer_count"] > 0:
            ratio = new_drawer_count / plan["existing_drawer_count"]
            if ratio < 0.5:
                print(
                    f"WARNING: drawer count dropped significantly "
                    f"({plan['existing_drawer_count']} -> {new_drawer_count}, "
                    f"{ratio:.0%}). Backup preserved at {backup_path}"
                )

        return {
            "rebuilt": True,
            "new_drawer_count": new_drawer_count,
            "backup_path": str(backup_path) if backup_path else plan["backup_path"],
            "dry_run": False,
        }

    except Exception as exc:
        if backup_path and backup_path.exists():
            if cfg.wings_dir.exists():
                shutil.rmtree(cfg.wings_dir)
            shutil.move(str(backup_path), str(cfg.wings_dir))
        if index_backup and index_backup.exists() and storage_path:
            if storage_path.exists():
                if storage_path.is_file():
                    storage_path.unlink()
                else:
                    shutil.rmtree(storage_path)
            if index_backup.is_file():
                shutil.copy2(index_backup, storage_path)
            else:
                shutil.copytree(index_backup, storage_path)
        if graph_backup and graph_backup.exists():
            shutil.copy2(graph_backup, cfg.graph_full_path)
        if isinstance(exc, RebuildError):
            raise
        raise RebuildError(f"Rebuild failed and was rolled back: {exc}") from exc
    finally:
        lock.release()
