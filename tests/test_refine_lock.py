"""v1.2.1 — per-JSONL refine lock + ledger recheck-after-claim.

Tests the `claim_jsonl_for_refine` gate that funnels all three refine
callers (session_end_hook, recall_briefing.run_refine_sync,
auto_refine.run) through a single coordination point so concurrent
workers can't produce duplicate Sessions/.md files for the same JSONL.
"""
from __future__ import annotations

import threading
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# claim_jsonl_for_refine — happy path + skip paths
# ---------------------------------------------------------------------------


def test_claim_succeeds_when_ledger_has_no_entry(tmp_path):
    from mnemos.refine_lock import claim_jsonl_for_refine

    jsonl = tmp_path / "abc.jsonl"
    jsonl.write_text("{}", encoding="utf-8")
    ledger = tmp_path / "processed.tsv"

    claim = claim_jsonl_for_refine(jsonl, ledger)
    assert claim is not None
    with claim:
        # Lock is held inside this block; nobody else can claim
        again = claim_jsonl_for_refine(jsonl, ledger)
        assert again is None, "second concurrent claim must be denied"

    # After the with-block exits, the lock is released and a fresh claim succeeds
    fresh = claim_jsonl_for_refine(jsonl, ledger)
    assert fresh is not None
    fresh.__exit__(None, None, None)


def test_claim_skips_when_ledger_has_ok_entry(tmp_path):
    from mnemos.refine_lock import claim_jsonl_for_refine

    jsonl = tmp_path / "abc.jsonl"
    jsonl.write_text("{}", encoding="utf-8")
    ledger = tmp_path / "processed.tsv"
    ledger.write_text(
        f"{jsonl}\tOK\t2026-04-28-test.md\n",
        encoding="utf-8",
    )

    assert claim_jsonl_for_refine(jsonl, ledger) is None


def test_claim_skips_when_ledger_has_skip_entry(tmp_path):
    """A SKIP entry is also a 'processed' marker; no point re-running."""
    from mnemos.refine_lock import claim_jsonl_for_refine

    jsonl = tmp_path / "abc.jsonl"
    jsonl.write_text("{}", encoding="utf-8")
    ledger = tmp_path / "processed.tsv"
    ledger.write_text(
        f"{jsonl}\tSKIP\tnoise-1-turn\n",
        encoding="utf-8",
    )

    assert claim_jsonl_for_refine(jsonl, ledger) is None


def test_claim_recheck_after_acquire_when_concurrent_writer_finishes(tmp_path, monkeypatch):
    """Worker A holds lock and finishes (writes OK to ledger). Worker B was
    blocked behind A; when B finally acquires the lock, the ledger now has
    A's OK entry — B must recheck and bail out instead of redoing the work.
    """
    from mnemos.refine_lock import claim_jsonl_for_refine

    jsonl = tmp_path / "abc.jsonl"
    jsonl.write_text("{}", encoding="utf-8")
    ledger = tmp_path / "processed.tsv"

    # Worker A's path: claim, write OK, release.
    claim_a = claim_jsonl_for_refine(jsonl, ledger)
    assert claim_a is not None
    with claim_a:
        with ledger.open("a", encoding="utf-8") as fh:
            fh.write(f"{jsonl}\tOK\t2026-04-28-worker-a.md\n")
    # Lock released.

    # Worker B claims AFTER A finished. Even though lock is free, the recheck
    # must observe A's OK entry and refuse the claim.
    assert claim_jsonl_for_refine(jsonl, ledger) is None


def test_lock_files_isolate_distinct_jsonls(tmp_path):
    """Two different JSONLs must not block each other — locks are per-stem."""
    from mnemos.refine_lock import claim_jsonl_for_refine

    jsonl_a = tmp_path / "aaa.jsonl"
    jsonl_a.write_text("{}", encoding="utf-8")
    jsonl_b = tmp_path / "bbb.jsonl"
    jsonl_b.write_text("{}", encoding="utf-8")
    ledger = tmp_path / "processed.tsv"

    claim_a = claim_jsonl_for_refine(jsonl_a, ledger)
    claim_b = claim_jsonl_for_refine(jsonl_b, ledger)

    assert claim_a is not None
    assert claim_b is not None
    claim_a.__exit__(None, None, None)
    claim_b.__exit__(None, None, None)


def test_concurrent_threads_only_one_claim_succeeds(tmp_path):
    """Stress: 10 threads race for the same JSONL. Exactly one wins."""
    from mnemos.refine_lock import claim_jsonl_for_refine

    jsonl = tmp_path / "abc.jsonl"
    jsonl.write_text("{}", encoding="utf-8")
    ledger = tmp_path / "processed.tsv"

    barrier = threading.Barrier(10)
    winners: list[bool] = []
    winners_lock = threading.Lock()

    def worker():
        barrier.wait()  # all threads start at the same instant
        claim = claim_jsonl_for_refine(jsonl, ledger)
        won = claim is not None
        if won:
            try:
                # Hold the lock briefly so other threads have a real chance to
                # observe the busy state before we release.
                import time
                time.sleep(0.05)
            finally:
                claim.__exit__(None, None, None)
        with winners_lock:
            winners.append(won)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sum(winners) == 1, f"expected exactly one winner, got {sum(winners)}"


# ---------------------------------------------------------------------------
# normalize_ledger — corruption recovery
# ---------------------------------------------------------------------------


def test_normalize_dedups_duplicate_ok_lines(tmp_path):
    from mnemos.refine_lock import normalize_ledger

    ledger = tmp_path / "processed.tsv"
    ledger.write_text(
        "C:/x/a.jsonl\tOK\t2026-04-28-aaa.md\n"
        "C:/x/a.jsonl\tOK\t2026-04-28-aaa.md\n"
        "C:/x/a.jsonl\tOK\t2026-04-28-bbb.md\n"
        "C:/x/b.jsonl\tOK\t2026-04-28-ccc.md\n",
        encoding="utf-8",
    )

    report = normalize_ledger(ledger, validate_paths=False)

    out = ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(out) == 2, f"expected 2 unique paths, got {out}"
    a_lines = [ln for ln in out if "a.jsonl" in ln]
    assert len(a_lines) == 1
    # Most-recent OK wins (last seen in original order)
    assert a_lines[0].endswith("2026-04-28-bbb.md")
    assert report["duplicates_dropped"] >= 2


def test_normalize_prefers_ok_over_skip_for_same_path(tmp_path):
    from mnemos.refine_lock import normalize_ledger

    ledger = tmp_path / "processed.tsv"
    ledger.write_text(
        "C:/x/a.jsonl\tSKIP\tnoise\n"
        "C:/x/a.jsonl\tOK\t2026-04-28-real.md\n",
        encoding="utf-8",
    )

    normalize_ledger(ledger, validate_paths=False)

    out = ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(out) == 1
    assert "OK" in out[0]
    assert "real.md" in out[0]


def test_normalize_repairs_tab_corrupted_line(tmp_path):
    """When two concurrent appends collide, TABs can be lost. The corrupted
    line looks like `<concat-of-path-fragments><filename>\\tOK\\t<slug>` with
    fewer than 3 TABs. Normalize should recover what it can — for lines that
    cannot be salvaged, drop them rather than crash."""
    from mnemos.refine_lock import normalize_ledger

    ledger = tmp_path / "processed.tsv"
    # Line 1: valid. Line 2: corrupted (no TAB at all). Line 3: valid.
    ledger.write_text(
        "C:/x/good.jsonl\tOK\t2026-04-28-good.md\n"
        "C:/x/junkOK2026-04-28-junk.md\n"
        "C:/x/other.jsonl\tOK\t2026-04-28-other.md\n",
        encoding="utf-8",
    )

    report = normalize_ledger(ledger, validate_paths=False)

    out = ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(out) == 2, f"corrupted line should be dropped, got {out}"
    assert any("good.jsonl" in ln for ln in out)
    assert any("other.jsonl" in ln for ln in out)
    assert report["malformed_dropped"] >= 1


def test_normalize_drops_entries_for_missing_jsonls(tmp_path):
    """Validate paths mode: drop entries whose JSONL no longer exists.
    Useful for periodic ledger hygiene; opt-in because it requires disk
    access for every entry."""
    from mnemos.refine_lock import normalize_ledger

    real_jsonl = tmp_path / "real.jsonl"
    real_jsonl.write_text("{}", encoding="utf-8")
    ledger = tmp_path / "processed.tsv"
    ledger.write_text(
        f"{real_jsonl}\tOK\t2026-04-28-real.md\n"
        "C:/dead-path/ghost.jsonl\tOK\t2026-04-28-ghost.md\n",
        encoding="utf-8",
    )

    report = normalize_ledger(ledger, validate_paths=True)

    out = ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(out) == 1
    assert "real" in out[0]
    assert report["dead_paths_dropped"] == 1


def test_normalize_writes_atomically(tmp_path):
    """The output must be tmp+rename so a crash mid-write doesn't leave the
    ledger empty. The presence of a `<ledger>.tmp` after the call would
    indicate a non-atomic write."""
    from mnemos.refine_lock import normalize_ledger

    ledger = tmp_path / "processed.tsv"
    ledger.write_text(
        "C:/x/a.jsonl\tOK\taaa.md\n",
        encoding="utf-8",
    )

    normalize_ledger(ledger, validate_paths=False)

    assert ledger.exists()
    assert not (tmp_path / "processed.tsv.tmp").exists(), \
        "tmp file must not survive a successful normalize"
