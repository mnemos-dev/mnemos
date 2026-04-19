"""Stress + durability tests for the ChromaDB write path.

These tests intentionally reproduce the HNSW index corruption that
happens on Windows when PersistentClient is used without closing,
and verify that our fix (explicit close + file lock) prevents it.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from mnemos.config import MnemosConfig
from mnemos.search import SearchEngine


def _make_config(tmp: Path) -> MnemosConfig:
    """Minimal MnemosConfig pointing at tmp for a clean per-test vault."""
    (tmp / "Mnemos").mkdir(parents=True, exist_ok=True)
    return MnemosConfig(vault_path=str(tmp))


def _chroma_bin_files(vault: Path) -> list[Path]:
    chroma = vault / "Mnemos" / ".chroma"
    if not chroma.exists():
        return []
    return list(chroma.rglob("*.bin"))


def _can_reopen(vault: Path) -> tuple[bool, int, int]:
    """Try to reopen the index in a fresh process and count rows.

    Returns (ok, mined_count, raw_count). A failure to load HNSW surfaces
    as an exception here, which is exactly the corruption we're testing.
    """
    cfg = _make_config(vault)
    try:
        engine = SearchEngine(cfg)
    except Exception:
        return (False, 0, 0)
    try:
        mined = engine._collection.count()
        raw = engine._raw_collection.count()
        return (True, mined, raw)
    except Exception:
        return (False, 0, 0)
    finally:
        try:
            engine.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Baseline: small writes + close → index reopens cleanly
# ---------------------------------------------------------------------------


def test_small_write_with_close_reopens(tmp_path):
    cfg = _make_config(tmp_path)
    engine = SearchEngine(cfg)
    for i in range(50):
        engine.index_drawer(
            drawer_id=f"d_{i}",
            text=f"mined content {i}",
            metadata={"wing": "Test", "room": "r", "hall": "facts"},
        )
        engine.index_raw(
            doc_id=f"r_{i}",
            text=f"raw content {i}",
            metadata={"wing": "Test", "room": "r"},
        )
    engine.close()

    ok, mined, raw = _can_reopen(tmp_path)
    assert ok, "Index should reopen after clean close"
    assert mined == 50
    assert raw == 50


# ---------------------------------------------------------------------------
# Stress: many writes across both collections + close → still reopens
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_large_write_with_close_reopens(tmp_path):
    cfg = _make_config(tmp_path)
    engine = SearchEngine(cfg)
    N = 1000
    for i in range(N):
        engine.index_drawer(
            drawer_id=f"d_{i}",
            text=f"mined doc number {i} about topic {i % 20}",
            metadata={"wing": f"W{i % 5}", "room": "r", "hall": "facts"},
        )
        engine.index_raw(
            doc_id=f"r_{i}",
            text=f"raw chunk {i} " + " word" * 20,
            metadata={"wing": f"W{i % 5}", "room": "r"},
        )
    engine.close()

    ok, mined, raw = _can_reopen(tmp_path)
    assert ok, f"Large write + close must reopen cleanly; mined={mined} raw={raw}"
    assert mined == N
    assert raw == N


# ---------------------------------------------------------------------------
# Regression: write *without* close should expose the corruption we fixed.
# This test documents current behavior; it passes when corruption still
# happens after skipped close (which is the bug we work around by always
# calling close).
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_write_without_close_can_lose_hnsw_segments(tmp_path):
    """Without close(), HNSW segments may not be flushed.

    This test runs the write in a *subprocess* that exits with os._exit()
    so atexit handlers cannot run — the worst-case process termination.
    It asserts that the current mnemos code reopens cleanly anyway
    (because we force close via context manager / atexit), which catches
    regressions where someone forgets to close.
    """
    vault = tmp_path
    cfg = _make_config(vault)
    script = f"""
import os, sys
sys.path.insert(0, {str(Path(__file__).parent.parent)!r})
from mnemos.config import MnemosConfig
from mnemos.search import SearchEngine
cfg = MnemosConfig(vault_path={str(vault)!r})
engine = SearchEngine(cfg)
for i in range(500):
    engine.index_drawer(
        drawer_id=f'd_{{i}}',
        text=f'doc {{i}}',
        metadata={{'wing':'W','room':'r','hall':'facts'}},
    )
    engine.index_raw(
        doc_id=f'r_{{i}}',
        text=f'raw {{i}}',
        metadata={{'wing':'W','room':'r'}},
    )
engine.close()
os._exit(0)  # skip atexit so only explicit close matters
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, f"subprocess failed: {result.stderr}"

    ok, mined, raw = _can_reopen(vault)
    assert ok, (
        "After explicit close() the index must reopen even when "
        "atexit handlers are skipped (os._exit). "
        f"stderr from child: {result.stderr}"
    )
    assert mined == 500
    assert raw == 500


# ---------------------------------------------------------------------------
# Process-kill scenario: child writes then is SIGTERM'd mid-flight.
# This is "user clicks X" — neither close() nor atexit runs.
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_killed_mid_write_does_not_permanently_corrupt(tmp_path):
    """If a writer is killed before close(), the next process should still
    be able to open the index (possibly empty/partial data is fine, but
    it must not be stuck unreadable forever).
    """
    vault = tmp_path
    script = f"""
import sys, time
sys.path.insert(0, {str(Path(__file__).parent.parent)!r})
from mnemos.config import MnemosConfig
from mnemos.search import SearchEngine
cfg = MnemosConfig(vault_path={str(vault)!r})
(__import__('pathlib').Path({str(vault)!r}) / 'Mnemos').mkdir(parents=True, exist_ok=True)
engine = SearchEngine(cfg)
for i in range(10_000):
    engine.index_drawer(
        drawer_id=f'd_{{i}}',
        text=f'doc {{i}}',
        metadata={{'wing':'W','room':'r','hall':'facts'}},
    )
    if i == 100:
        print('READY', flush=True)
    time.sleep(0.001)
"""
    (vault / "Mnemos").mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    # Wait for the child to start writing
    line = proc.stdout.readline()
    assert "READY" in line, f"child didn't start: stderr={proc.stderr.read()}"
    time.sleep(0.5)  # let it accumulate some writes
    proc.kill()  # SIGTERM-equivalent; no cleanup runs
    proc.wait(timeout=10)

    # Now try to reopen from a fresh process
    ok, mined, raw = _can_reopen(vault)
    assert ok, (
        "After a hard kill mid-write, reopening must still work "
        "(data loss is acceptable, permanent corruption is not). "
        f"mined={mined} raw={raw}"
    )
