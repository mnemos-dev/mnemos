"""Tests for backend storage introspection (v0.3.1 task 3.14e).

Each backend must expose:
  - ``storage_path()`` → Path | None  (None in memory mode)
  - ``get_stats()["storage_bytes"]`` → int  (0 when in memory)

These feed the `mnemos status` backend summary line:

    Backend: sqlite-vec (search.sqlite3 · 8027 drawers · 42.3 MB)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mnemos.config import MnemosConfig
from mnemos.search import ChromaBackend, SqliteVecBackend


# ---------------------------------------------------------------------------
# storage_path
# ---------------------------------------------------------------------------


def test_chroma_backend_storage_path_points_at_chroma_dir(tmp_path: Path) -> None:
    """Persistent ChromaBackend returns its .chroma directory path."""
    cfg = MnemosConfig(vault_path=str(tmp_path), search_backend="chromadb")
    backend = ChromaBackend(cfg, in_memory=False)
    try:
        path = backend.storage_path()
        assert path is not None
        assert path == cfg.chromadb_full_path
        assert path.exists() and path.is_dir()
    finally:
        backend.close()


def test_sqlite_vec_backend_storage_path_points_at_sqlite_file(tmp_path: Path) -> None:
    """Persistent SqliteVecBackend returns its search.sqlite3 file path."""
    cfg = MnemosConfig(vault_path=str(tmp_path), search_backend="sqlite-vec")
    backend = SqliteVecBackend(cfg, in_memory=False)
    try:
        path = backend.storage_path()
        assert path is not None
        assert path.name == "search.sqlite3"
        assert path.exists() and path.is_file()
    finally:
        backend.close()


def test_chroma_backend_storage_path_is_none_in_memory(tmp_path: Path) -> None:
    cfg = MnemosConfig(vault_path=str(tmp_path), search_backend="chromadb")
    backend = ChromaBackend(cfg, in_memory=True)
    try:
        assert backend.storage_path() is None
    finally:
        backend.close()


def test_sqlite_vec_backend_storage_path_is_none_in_memory(tmp_path: Path) -> None:
    cfg = MnemosConfig(vault_path=str(tmp_path), search_backend="sqlite-vec")
    backend = SqliteVecBackend(cfg, in_memory=True)
    try:
        assert backend.storage_path() is None
    finally:
        backend.close()


# ---------------------------------------------------------------------------
# storage_bytes in get_stats()
# ---------------------------------------------------------------------------


def test_chroma_get_stats_reports_storage_bytes(tmp_path: Path) -> None:
    """A freshly created ChromaDB on disk should report non-zero storage_bytes."""
    cfg = MnemosConfig(vault_path=str(tmp_path), search_backend="chromadb")
    backend = ChromaBackend(cfg, in_memory=False)
    try:
        backend.index_drawer(
            drawer_id="s1",
            text="some content to force a flush",
            metadata={"wing": "W", "room": "R", "hall": "facts"},
        )
        stats = backend.get_stats()
        assert "storage_bytes" in stats
        assert isinstance(stats["storage_bytes"], int)
        assert stats["storage_bytes"] > 0
    finally:
        backend.close()


def test_sqlite_vec_get_stats_reports_storage_bytes(tmp_path: Path) -> None:
    """A freshly created sqlite-vec DB should report non-zero storage_bytes."""
    cfg = MnemosConfig(vault_path=str(tmp_path), search_backend="sqlite-vec")
    backend = SqliteVecBackend(cfg, in_memory=False)
    try:
        backend.index_drawer(
            drawer_id="s1",
            text="some content to force a flush",
            metadata={"wing": "W", "room": "R", "hall": "facts"},
        )
        stats = backend.get_stats()
        assert "storage_bytes" in stats
        assert isinstance(stats["storage_bytes"], int)
        assert stats["storage_bytes"] > 0
    finally:
        backend.close()


def test_get_stats_storage_bytes_is_zero_in_memory(tmp_path: Path) -> None:
    """In-memory backends have no on-disk footprint."""
    cfg = MnemosConfig(vault_path=str(tmp_path), search_backend="chromadb")
    chroma = ChromaBackend(cfg, in_memory=True)
    try:
        assert chroma.get_stats()["storage_bytes"] == 0
    finally:
        chroma.close()

    cfg2 = MnemosConfig(vault_path=str(tmp_path), search_backend="sqlite-vec")
    sqlite = SqliteVecBackend(cfg2, in_memory=True)
    try:
        assert sqlite.get_stats()["storage_bytes"] == 0
    finally:
        sqlite.close()


# ---------------------------------------------------------------------------
# Server + CLI integration
# ---------------------------------------------------------------------------


def test_handle_status_includes_backend_block(tmp_path: Path) -> None:
    """MnemosApp.handle_status() returns a `backend` dict with name/path/bytes."""
    from mnemos.server import MnemosApp

    cfg = MnemosConfig(vault_path=str(tmp_path), search_backend="sqlite-vec")
    app = MnemosApp(cfg)
    try:
        app.palace.ensure_structure()
        app.search_engine.index_drawer(
            drawer_id="s1",
            text="seed the index to produce non-zero storage bytes",
            metadata={"wing": "W", "room": "R", "hall": "facts"},
        )
        result = app.handle_status()
        assert "backend" in result
        b = result["backend"]
        assert b["name"] == "sqlite-vec"
        assert b["path"] and "search.sqlite3" in b["path"]
        assert b["storage_bytes"] > 0
    finally:
        app.close()


def test_cmd_status_prints_backend_summary_line(tmp_path: Path, capsys) -> None:
    """CLI status command prints a human-readable Backend line on stdout."""
    import argparse

    from mnemos.cli import cmd_status
    from mnemos.server import MnemosApp

    cfg = MnemosConfig(vault_path=str(tmp_path), search_backend="sqlite-vec")
    app = MnemosApp(cfg)
    try:
        app.palace.ensure_structure()
        app.search_engine.index_drawer(
            drawer_id="s1",
            text="seed drawer",
            metadata={"wing": "W", "room": "R", "hall": "facts"},
        )
    finally:
        app.close()

    # Write config so load_config picks up the sqlite-vec backend
    (tmp_path / "mnemos.yaml").write_text(
        "search_backend: sqlite-vec\n", encoding="utf-8",
    )

    args = argparse.Namespace(vault=str(tmp_path))
    cmd_status(args)

    captured = capsys.readouterr().out
    assert "Backend:" in captured
    assert "sqlite-vec" in captured
    assert "search.sqlite3" in captured
    assert "drawer" in captured.lower()  # drawer count rendered
