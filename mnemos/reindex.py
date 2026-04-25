"""Reindex: rebuild vector index from Sessions, optional backend switch.

v1.0 narrative-first pivot: the vault's ``Sessions/*.md`` files are the
ground truth. This module rebuilds the vector index from scratch by walking
those files and bulk-inserting them into the configured search backend.

Optionally swaps the ``search_backend`` field in ``mnemos.yaml`` before
rebuilding (e.g. ``mnemos reindex --backend sqlite-vec`` to migrate off
ChromaDB after an HNSW corruption). Existing on-disk index is backed up
unless ``no_backup=True`` so users can roll back if the rebuild itself
fails.
"""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from mnemos.config import load_config


class ReindexError(Exception):
    """Raised when reindex cannot proceed (missing yaml, unknown backend, …)."""


def reindex(
    vault: Path,
    backend: Optional[str] = None,
    no_backup: bool = False,
) -> dict:
    """Rebuild vector index from ``<vault>/Sessions``.

    Args:
        vault: Mnemos vault root (must contain ``mnemos.yaml``).
        backend: Override ``search_backend`` in ``mnemos.yaml`` before rebuild.
            Must be ``"chromadb"`` or ``"sqlite-vec"``.
        no_backup: Skip pre-rebuild backup of existing on-disk index.

    Returns:
        Stats dict with keys ``session_count``, ``backend``, ``backup_path``.
    """
    vault = Path(vault)
    yaml_path = vault / "mnemos.yaml"
    if not yaml_path.exists():
        raise ReindexError(f"no mnemos.yaml at {yaml_path}")

    cfg_data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}

    if backend is not None:
        if backend not in ("chromadb", "sqlite-vec"):
            raise ReindexError(f"unknown backend: {backend}")
        cfg_data["search_backend"] = backend
        yaml_path.write_text(
            yaml.safe_dump(cfg_data, sort_keys=False), encoding="utf-8"
        )

    selected_backend = cfg_data.get("search_backend", "chromadb")

    storage_root = vault / "Mnemos"
    storage_root.mkdir(exist_ok=True)

    backup_path: Optional[Path] = None
    if not no_backup:
        backup_path = _backup_storage(storage_root, selected_backend)

    # After backup (or skipped backup), wipe the live storage so SearchEngine
    # can reinitialise cleanly even if the previous file was corrupted (HNSW
    # crash, broken sqlite, etc.) — the whole point of reindex is recovery.
    _wipe_storage(storage_root, selected_backend)

    # Build a config rooted at this vault and instantiate the configured
    # backend via the SearchEngine factory. drop_and_reinit() empties both
    # mined+raw collections so we can repopulate from Sessions.
    cfg = load_config(str(vault))
    from mnemos.search import SearchEngine
    engine = SearchEngine(cfg)
    try:
        engine.drop_and_reinit()

        sessions_dir = vault / "Sessions"
        sessions = sorted(sessions_dir.glob("*.md")) if sessions_dir.exists() else []
        if sessions:
            items: list[tuple[str, str, dict]] = []
            for session in sessions:
                content = session.read_text(encoding="utf-8")
                doc_id = engine.raw_doc_id(str(session))
                metadata = {
                    "path": str(session.relative_to(vault)).replace("\\", "/"),
                    "type": "session",
                }
                items.append((doc_id, content, metadata))
            engine.index_raw_bulk(items)
    finally:
        engine.close()

    return {
        "session_count": len(sessions),
        "backend": selected_backend,
        "backup_path": str(backup_path) if backup_path else None,
    }


def _wipe_storage(storage_root: Path, backend: str) -> None:
    """Remove the live index file/dir so a fresh backend can be opened.

    Backups are taken before this is called; this is the destructive step
    that lets reindex recover from a corrupted prior index.
    """
    if backend == "sqlite-vec":
        sqlite_file = storage_root / "search.sqlite3"
        if sqlite_file.exists():
            sqlite_file.unlink()
    elif backend == "chromadb":
        chroma_dir = storage_root / ".chroma"
        if chroma_dir.exists():
            shutil.rmtree(chroma_dir)


def _backup_storage(storage_root: Path, backend: str) -> Optional[Path]:
    """Backup existing index files. Returns the .bak path, or None if nothing to back up."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    if backend == "sqlite-vec":
        sqlite_file = storage_root / "search.sqlite3"
        if not sqlite_file.exists():
            return None
        bak = storage_root / f"search.sqlite3.bak-{timestamp}"
        shutil.copy2(sqlite_file, bak)
        return bak
    elif backend == "chromadb":
        chroma_dir = storage_root / ".chroma"
        if not chroma_dir.exists():
            return None
        bak = storage_root / f".chroma.bak-{timestamp}"
        shutil.copytree(chroma_dir, bak)
        return bak
    return None
