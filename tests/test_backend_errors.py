"""Tests for mnemos.errors + SearchEngine init error wrapping (v0.3.1 task 3.14c).

Backend init failures (ChromaDB HNSW load errors, sqlite-vec DatabaseError,
permission issues) must surface as BackendInitError with an actionable
message suggesting `mnemos migrate --backend <other>`. Original exception
is preserved via __cause__ so `--verbose` paths can still show it.
"""
from __future__ import annotations

import pytest

from mnemos.config import MnemosConfig
from mnemos.errors import BackendInitError, MnemosError


# ---------------------------------------------------------------------------
# Error class shape
# ---------------------------------------------------------------------------


def test_backend_init_error_inherits_from_mnemos_error() -> None:
    """BackendInitError must be a subclass of MnemosError for blanket catches."""
    assert issubclass(BackendInitError, MnemosError)
    assert issubclass(MnemosError, Exception)


def test_backend_init_error_carries_backend_and_suggestion() -> None:
    """Constructor exposes the failed backend and the migrate target."""
    err = BackendInitError(
        backend="chromadb",
        cause=RuntimeError("HNSW corrupted"),
    )
    assert err.backend == "chromadb"
    assert err.alternative == "sqlite-vec"
    msg = str(err)
    assert "chromadb" in msg
    assert "mnemos migrate --backend sqlite-vec" in msg
    assert "HNSW corrupted" in msg  # cause visible in summary


def test_backend_init_error_alternative_flips_for_sqlite_vec() -> None:
    """When sqlite-vec fails, migrate suggestion points back to chromadb."""
    err = BackendInitError(
        backend="sqlite-vec",
        cause=RuntimeError("database is malformed"),
    )
    assert err.alternative == "chromadb"
    assert "mnemos migrate --backend chromadb" in str(err)


def test_backend_init_error_preserves_cause_chain() -> None:
    """raise ... from cause must keep original traceback accessible."""
    original = RuntimeError("HNSW corrupted")
    try:
        raise BackendInitError(backend="chromadb", cause=original) from original
    except BackendInitError as exc:
        assert exc.__cause__ is original


# ---------------------------------------------------------------------------
# SearchEngine factory wrapping
# ---------------------------------------------------------------------------


def test_search_engine_wraps_chromadb_failure(monkeypatch, tmp_path) -> None:
    """A ChromaDB PersistentClient exception surfaces as BackendInitError."""
    import chromadb

    def boom(*args, **kwargs):
        raise RuntimeError("HNSW index corrupted — binary missing")

    monkeypatch.setattr(chromadb, "PersistentClient", boom)

    cfg = MnemosConfig(vault_path=str(tmp_path), search_backend="chromadb")

    from mnemos.search import SearchEngine

    with pytest.raises(BackendInitError) as exc_info:
        SearchEngine(cfg, in_memory=False)

    err = exc_info.value
    assert err.backend == "chromadb"
    assert "sqlite-vec" in str(err)
    assert "HNSW" in str(err)  # original cause detail included


def test_search_engine_wraps_sqlite_vec_failure(monkeypatch, tmp_path) -> None:
    """A sqlite-vec init exception surfaces as BackendInitError."""
    import sqlite_vec

    def boom(*args, **kwargs):
        raise RuntimeError("sqlite-vec extension load failed")

    monkeypatch.setattr(sqlite_vec, "load", boom)

    cfg = MnemosConfig(vault_path=str(tmp_path), search_backend="sqlite-vec")

    from mnemos.search import SearchEngine

    with pytest.raises(BackendInitError) as exc_info:
        SearchEngine(cfg, in_memory=False)

    err = exc_info.value
    assert err.backend == "sqlite-vec"
    assert "chromadb" in str(err)


def test_search_engine_does_not_wrap_unknown_backend_error() -> None:
    """Bad config (unknown backend name) keeps the original ValueError.

    BackendInitError is for *runtime* init failures on a valid backend —
    config typos are a different class of problem.
    """
    cfg = MnemosConfig(vault_path="", search_backend="no-such-backend")

    from mnemos.search import SearchEngine

    with pytest.raises(ValueError):
        SearchEngine(cfg, in_memory=True)
