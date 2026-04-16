"""Auto-refine hook: SessionStart orchestration for last-3 JSONL refinement."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Sequence

from filelock import FileLock, Timeout

from mnemos.pending import PendingState
from mnemos.pending import load as pending_load
from mnemos.pending import save as pending_save

DEFAULT_LEDGER_SUFFIX = Path(".claude/skills/mnemos-refine-transcripts/state/processed.tsv")
REMINDER_INTERVAL_DAYS = 7
STATUS_FILENAME = ".mnemos-hook-status.json"
HOOK_LOG_FILENAME = ".mnemos-hook.log"
HOOK_LOCK_FILENAME = ".mnemos-hook.lock"

Runner = Callable[[Sequence[str]], int]


def resolve_ledger_path() -> Path:
    """Return the refine-skill ledger path.

    Honors `MNEMOS_REFINE_LEDGER` if set. Otherwise falls back to the canonical
    junction target under the user home directory.
    """
    override = os.environ.get("MNEMOS_REFINE_LEDGER")
    if override:
        return Path(override)
    return Path.home() / DEFAULT_LEDGER_SUFFIX


def _read_ledger_paths(ledger_path: Path) -> set[str]:
    """Return the set of source-JSONL paths recorded in the refine-skill ledger.

    Ledger format is one TSV line per processed JSONL:
    `<source_path>\t<status>\t<note_or_reason>` where status is OK or SKIP.
    Empty or missing file → empty set. Paths are normalised via Path()/str()
    so backslash/slash and case differences between ledger writer and reader
    don't cause spurious re-picks.
    """
    if not ledger_path.exists():
        return set()

    paths: set[str] = set()
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        cols = line.split("\t")
        if not cols or not cols[0].strip():
            continue
        raw = cols[0].strip()
        paths.add(str(Path(raw)))
    return paths


def pick_recent_jsonls(projects_dir: Path, ledger_path: Path, n: int = 3) -> list[Path]:
    """Return up to `n` most-recent (by mtime) JSONLs not already in the ledger."""
    if not projects_dir.exists():
        return []

    ledger_paths = _read_ledger_paths(ledger_path)
    candidates = sorted(
        (p for p in projects_dir.rglob("*.jsonl") if not _is_subagent_jsonl(p)),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    picked: list[Path] = []
    for candidate in candidates:
        if str(candidate) in ledger_paths:
            continue
        picked.append(candidate)
        if len(picked) >= n:
            break
    return picked


def compute_backlog(projects_dir: Path, ledger_path: Path) -> int:
    """Count JSONLs under `projects_dir` that are not listed in the ledger.

    Uses the same path normalisation as `pick_recent_jsonls` so counts stay
    consistent between the picker and the backlog reminder.
    """
    if not projects_dir.exists():
        return 0

    ledger_paths = _read_ledger_paths(ledger_path)
    total = 0
    for candidate in projects_dir.rglob("*.jsonl"):
        if _is_subagent_jsonl(candidate):
            continue
        if str(candidate) not in ledger_paths:
            total += 1
    return total


def should_show_reminder(state: PendingState, today: datetime, backlog: int) -> bool:
    """Decide whether to show the backlog reminder this session.

    Rules:
    - backlog <= 0 → never
    - no `backlog_reminder_last_shown` → yes (first run)
    - otherwise → yes only if ≥ REMINDER_INTERVAL_DAYS since last shown
    """
    if backlog <= 0:
        return False
    if not state.backlog_reminder_last_shown:
        return True
    last = datetime.fromisoformat(state.backlog_reminder_last_shown)
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return today - last >= timedelta(days=REMINDER_INTERVAL_DAYS)


def write_status(
    vault: Path,
    phase: str,
    current: int,
    total: int,
    backlog: int,
    reminder_active: bool,
    started_at: str,
) -> Path:
    """Atomically write the statusline state file (tmp + os.replace)."""
    path = Path(vault) / STATUS_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "phase": phase,
        "current": current,
        "total": total,
        "backlog": backlog,
        "reminder_active": reminder_active,
        "started_at": started_at,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    fd, tmp_name = tempfile.mkstemp(prefix=".mnemos-hook-status.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise

    return path


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def _is_subagent_jsonl(path: Path) -> bool:
    """True if the JSONL is a subagent transcript (nested under /subagents/).

    Claude Code writes subagent logs under `<project>/<session>/subagents/agent-*.jsonl`.
    The refine-skill default filter skips these — picker should match that default so
    hook runs don't waste `claude --print` invocations on files the skill will SKIP.
    """
    return "subagents" in path.parts


def _default_runner(cmd: Sequence[str]) -> int:
    """Invoke a subprocess, return exit code.

    For `claude` invocations, strip `ANTHROPIC_API_KEY` from the environment so
    the subprocess falls back to OAuth/Claude Code subscription auth instead of
    burning the user's API quota. Pilot finding (2026-04-16): when both auths
    are available, claude prefers the API key — which silently fails with
    'Credit balance too low' once the API quota runs out, even though the
    user's interactive Claude Code session still works fine on subscription.
    """
    kwargs: dict = {}
    if os.name == "nt":
        CREATE_NO_WINDOW = 0x08000000
        kwargs["creationflags"] = CREATE_NO_WINDOW
    if cmd and cmd[0] == "claude":
        env = os.environ.copy()
        env.pop("ANTHROPIC_API_KEY", None)
        kwargs["env"] = env
    return subprocess.call(list(cmd), **kwargs)


def run(
    vault: Path,
    projects_dir: Path,
    ledger_path: Path,
    picked: list[Path],
    reminder_active: bool,
    started_at: str,
    runner: Runner | None = None,
) -> None:
    """Background orchestrator: refine each picked JSONL, mine, update state.

    Acquires a filelock advisory lock at <vault>/.mnemos-hook.lock to avoid
    concurrent auto-refine runs from overlapping sessions.
    """
    runner = runner or _default_runner
    lock = FileLock(str(Path(vault) / HOOK_LOCK_FILENAME), timeout=1)

    try:
        with lock:
            _run_locked(
                vault=vault,
                projects_dir=projects_dir,
                ledger_path=ledger_path,
                picked=picked,
                reminder_active=reminder_active,
                started_at=started_at,
                runner=runner,
            )
    except Timeout:
        backlog = compute_backlog(projects_dir, ledger_path)
        write_status(vault, "busy", 0, 0, backlog, False, started_at)


def _run_locked(
    *,
    vault: Path,
    projects_dir: Path,
    ledger_path: Path,
    picked: list[Path],
    reminder_active: bool,
    started_at: str,
    runner: Runner,
) -> None:
    total = len(picked)
    log_path = Path(vault) / HOOK_LOG_FILENAME

    for i, jsonl in enumerate(picked, start=1):
        backlog = compute_backlog(projects_dir, ledger_path)
        write_status(vault, "refining", i, total, backlog, reminder_active, started_at)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] refine {jsonl}\n")
        rc = runner([
            "claude",
            "--print",
            "--dangerously-skip-permissions",
            f"/mnemos-refine-transcripts {jsonl}",
        ])
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"  exit={rc}\n")

    backlog = compute_backlog(projects_dir, ledger_path)
    write_status(vault, "mining", total, total, backlog, reminder_active, started_at)
    sessions_dir = Path(vault) / "Sessions"
    rc = runner([sys.executable, "-m", "mnemos.cli", "--vault", str(vault), "mine", str(sessions_dir)])
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"  mine exit={rc}\n")

    if reminder_active:
        state = pending_load(vault)
        state.backlog_reminder_last_shown = datetime.now(timezone.utc).isoformat(timespec="seconds")
        pending_save(vault, state)

    backlog = compute_backlog(projects_dir, ledger_path)
    write_status(vault, "idle", total, total, backlog, False, started_at)
