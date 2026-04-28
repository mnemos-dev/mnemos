"""v1.2.1 — per-JSONL refine coordination.

The `claim_jsonl_for_refine` gate funnels every refine entry point
(SessionEnd worker, recall_briefing.run_refine_sync, auto_refine.run)
through one coordination point. Concurrent workers race for the same
JSONL filelock; whoever loses observes the winner's ledger entry on
recheck and bails out cleanly. Without this gate, the LLM produces
non-deterministic slugs and two parallel `claude --print` invocations
either silently overwrite each other (data loss) or persist as
duplicate Sessions/.md siblings.

`normalize_ledger` is the one-shot recovery CLI for ledgers that were
already corrupted by pre-v1.2.1 concurrent appends.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from filelock import FileLock, Timeout

# Where per-JSONL lock files live, relative to the ledger directory.
_LOCKS_SUBDIR = "locks"


def _locks_dir(ledger: Path) -> Path:
    return ledger.parent / _LOCKS_SUBDIR


def _lock_path_for(ledger: Path, jsonl: Path) -> Path:
    return _locks_dir(ledger) / f"{jsonl.stem}.lock"


def _ledger_has_entry(ledger: Path, jsonl: Path) -> bool:
    """True iff `ledger` has an OK or SKIP line for the given JSONL.

    Uses the same parser semantics as `recall_briefing.load_refine_ledger_jsonls`
    — both OK and SKIP count as "processed" so we don't re-run noise
    transcripts on every hook fire. Tolerates malformed lines (skipped).
    """
    if not ledger.exists():
        return False
    target = str(jsonl)
    try:
        with ledger.open("r", encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                parts = raw.rstrip("\r\n").split("\t")
                if len(parts) < 3:
                    continue
                if parts[1] not in ("OK", "SKIP"):
                    continue
                if parts[0] == target:
                    return True
    except OSError:
        return False
    return False


@contextmanager
def _hold_filelock(lock_path: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(lock_path), timeout=0)
    lock.acquire()
    try:
        yield
    finally:
        try:
            lock.release()
        except Exception:
            pass


def claim_jsonl_for_refine(jsonl: Path, ledger: Path):
    """Try to claim `jsonl` for refinement.

    Returns a context manager (lock held) when the caller may proceed
    with `claude --print`. Returns `None` when:
    - The ledger already records an OK or SKIP entry for this JSONL
      (someone else finished — even before any lock attempt).
    - Another worker currently holds the per-JSONL filelock.
    - After acquiring the lock, a recheck reveals that another worker
      finished between the initial scan and the lock acquire.

    The lock backend is `filelock.FileLock` keyed on the JSONL stem,
    stored under `<ledger-dir>/locks/<stem>.lock`. The directory is
    created on first use.
    """
    # Pre-acquire fast path: avoid creating a lock file for already-finished work
    if _ledger_has_entry(ledger, jsonl):
        return None

    lock_path = _lock_path_for(ledger, jsonl)
    try:
        cm = _hold_filelock(lock_path)
        cm.__enter__()
    except Timeout:
        return None
    except OSError:
        # Filesystem error creating the lock dir / file — degrade open
        return None

    # Recheck inside the lock: a competing worker may have finished while we
    # were waiting for the OS to grant us the file lock.
    if _ledger_has_entry(ledger, jsonl):
        try:
            cm.__exit__(None, None, None)
        except Exception:
            pass
        return None

    # Caller now owns the lock. Wrap the cm in a tiny class so the caller
    # can use `with claim:` ergonomically AND dispatch lock release through
    # the same exit hook the contextmanager would.
    class _Claim:
        def __enter__(self_inner):
            return self_inner

        def __exit__(self_inner, exc_type, exc, tb):
            try:
                cm.__exit__(exc_type, exc, tb)
            except Exception:
                pass
            return False

    return _Claim()


# ---------------------------------------------------------------------------
# Ledger normalize — recovery from pre-v1.2.1 corruption
# ---------------------------------------------------------------------------


def normalize_ledger(ledger: Path, validate_paths: bool = False) -> dict:
    """One-shot ledger repair.

    - Drops lines that don't have exactly 3 tab-separated columns
      (the typical fingerprint of a concurrent-append collision that
      ate a TAB).
    - Dedups duplicate path entries; for each path the most-recent OK
      wins (an OK supersedes any earlier SKIP for the same path).
    - When `validate_paths=True`, drops entries whose JSONL no longer
      exists on disk.
    - Writes the result atomically (tmp + rename).

    Returns a small report dict with counts.
    """
    if not ledger.exists():
        return {
            "input_lines": 0,
            "kept": 0,
            "malformed_dropped": 0,
            "duplicates_dropped": 0,
            "dead_paths_dropped": 0,
        }

    raw_lines = ledger.read_text(encoding="utf-8", errors="replace").splitlines()
    input_n = len(raw_lines)

    # First pass: parse + filter malformed
    parsed: list[tuple[str, str, str]] = []
    malformed = 0
    for line in raw_lines:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            malformed += 1
            continue
        if parts[1] not in ("OK", "SKIP"):
            malformed += 1
            continue
        parsed.append((parts[0], parts[1], parts[2]))

    # Second pass: dedup. "Most recent OK wins; OK > SKIP for the same path."
    # Iterate in original order; for each path, keep the latest entry but
    # prefer OK over SKIP regardless of position.
    keep: dict[str, tuple[str, str, str]] = {}
    duplicates = 0
    for path, status, meta in parsed:
        prior = keep.get(path)
        if prior is None:
            keep[path] = (path, status, meta)
            continue
        duplicates += 1
        prior_status = prior[1]
        # OK always beats SKIP. Among same-status entries, latest wins.
        if status == "OK" and prior_status != "OK":
            keep[path] = (path, status, meta)
        elif status == prior_status:
            keep[path] = (path, status, meta)
        # else: prior is OK and current is SKIP → keep prior

    # Third pass (optional): drop entries whose JSONL no longer exists
    dead = 0
    if validate_paths:
        alive: dict[str, tuple[str, str, str]] = {}
        for path, status, meta in keep.values():
            try:
                if Path(path).exists():
                    alive[path] = (path, status, meta)
                else:
                    dead += 1
            except OSError:
                dead += 1
        keep = alive

    # Atomic write: tmp + rename
    tmp = ledger.with_suffix(ledger.suffix + ".tmp")
    out = "\n".join("\t".join(t) for t in keep.values())
    if out:
        out += "\n"
    tmp.write_text(out, encoding="utf-8")
    tmp.replace(ledger)

    return {
        "input_lines": input_n,
        "kept": len(keep),
        "malformed_dropped": malformed,
        "duplicates_dropped": duplicates,
        "dead_paths_dropped": dead,
    }
