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

# Sessions with fewer than this many real user-typed turns are treated as
# noise and excluded from picker + backlog. The author's vault grew a 150+
# "backlog" of /clear→mnemos resume sessions (1-2 turns each) that the
# refine-skill correctly SKIPped — but each round still burned a 30-60s
# `claude --print` invocation for zero gain. v0.3 task 3.11 raises the bar
# to 3 turns: 1 = pure noise, 2 = borderline, 3+ = real back-and-forth
# worth handing to the skill.
MIN_USER_TURNS = 3
_USER_TURN_SCAN_LIMIT = 500  # Scan at most N lines — 3 turns fit in well under 100 in practice.

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


def _count_user_turns(path: Path, max_lines: int = _USER_TURN_SCAN_LIMIT) -> int:
    """Return the number of real user-typed turns in a Claude Code JSONL.

    Claude Code stores tool results as `type=user` messages too, so a naive
    substring count would treat tool-heavy 1-turn sessions as N-turn — exactly
    what the v0.3.11 filter is trying to avoid. We JSON-parse each candidate
    line and skip messages whose content is a list of `tool_result` blocks.

    Reads up to `max_lines` for cheapness on large transcripts: 3 turns
    almost always appear in the first 100 lines, so 500 is a generous cap.
    Missing/unreadable file → 0 (caller treats as too-short).
    """
    if not path.exists():
        return 0
    count = 0
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            for i, line in enumerate(fh):
                if i >= max_lines:
                    break
                line = line.strip()
                if not line or '"type":"user"' not in line.replace(" ", ""):
                    # Cheap pre-filter: most non-user lines bail here.
                    continue
                try:
                    obj = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if obj.get("type") != "user":
                    continue
                msg = obj.get("message") or {}
                content = msg.get("content")
                if isinstance(content, list) and any(
                    isinstance(b, dict) and b.get("type") == "tool_result" for b in content
                ):
                    # Auto-generated tool result, not a real user turn.
                    continue
                count += 1
    except OSError:
        return 0
    return count


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


def pick_recent_jsonls(
    projects_dir: Path,
    ledger_path: Path,
    n: int = 3,
    exclude: set[str] | None = None,
    min_user_turns: int = MIN_USER_TURNS,
) -> list[Path]:
    """Return up to `n` most-recent (by mtime) JSONLs not already in the ledger.

    `exclude` is a set of path strings to filter out (typically the current
    session's `transcript_path` so we never refine an in-progress conversation —
    doing so would mark it OK in the ledger and silently drop the rest of the
    transcript). Path strings are normalised via Path() so backslash/slash
    differences between caller and stored values don't leak.

    `min_user_turns` (v0.3.11) drops candidates with fewer real user turns —
    pure resume / 1-instruction sessions that the refine-skill always SKIPs.
    Pass `0` to opt out (used by tests of orthogonal behavior). Threshold check
    happens last so subagent + ledger + exclude filters short-circuit the
    relatively-expensive file scan.
    """
    if not projects_dir.exists():
        return []

    ledger_paths = _read_ledger_paths(ledger_path)
    excluded = {str(Path(p)) for p in (exclude or set())}
    candidates = sorted(
        (p for p in projects_dir.rglob("*.jsonl") if not _is_subagent_jsonl(p)),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    picked: list[Path] = []
    for candidate in candidates:
        key = str(candidate)
        if key in ledger_paths or key in excluded:
            continue
        if min_user_turns > 0 and _count_user_turns(candidate) < min_user_turns:
            continue
        picked.append(candidate)
        if len(picked) >= n:
            break
    return picked


def compute_backlog(
    projects_dir: Path,
    ledger_path: Path,
    min_user_turns: int = MIN_USER_TURNS,
) -> int:
    """Count JSONLs under `projects_dir` that are not listed in the ledger.

    Uses the same path normalisation as `pick_recent_jsonls` so counts stay
    consistent between the picker and the backlog reminder. Same v0.3.11
    `min_user_turns` filter applies — backlog reflects *processable* work, not
    every JSONL sitting on disk. Without this, a 150-backlog of resume-noise
    sessions would never shrink because the picker keeps draining noise that
    new sessions instantly replace.
    """
    if not projects_dir.exists():
        return 0

    ledger_paths = _read_ledger_paths(ledger_path)
    total = 0
    for candidate in projects_dir.rglob("*.jsonl"):
        if _is_subagent_jsonl(candidate):
            continue
        if str(candidate) in ledger_paths:
            continue
        if min_user_turns > 0 and _count_user_turns(candidate) < min_user_turns:
            continue
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
    last_outcome: str | None = None,
    last_finished_at: str | None = None,
    last_ok: int | None = None,
    last_skip: int | None = None,
) -> Path:
    """Atomically write the statusline state file (tmp + os.replace).

    `last_outcome` ("ok" / "skip" / "noop" / "failed") and `last_finished_at` are
    written only when caller passes them — typically on the final `idle` transition
    so the snippet can render "last refine Xm ago · N notes · OK" instead of going
    silent immediately.

    `last_ok` / `last_skip` (v0.3.11) are per-round counters the snippet uses to
    distinguish "3 notes · OK" (3 real notes added) from "0 notes (3 skipped)"
    (skill correctly rejected all picks). When unset, the snippet falls back to
    the older `total` + `last_outcome` rendering for backward compat.
    """
    path = Path(vault) / STATUS_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)

    payload: dict = {
        "phase": phase,
        "current": current,
        "total": total,
        "backlog": backlog,
        "reminder_active": reminder_active,
        "started_at": started_at,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if last_outcome is not None:
        payload["last_outcome"] = last_outcome
    if last_finished_at is not None:
        payload["last_finished_at"] = last_finished_at
    if last_ok is not None:
        payload["last_ok"] = last_ok
    if last_skip is not None:
        payload["last_skip"] = last_skip

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


def _latest_outcome_for_path(ledger_path: Path, target: Path) -> str | None:
    """Return the most-recent status (`OK` / `SKIP` / etc.) the ledger holds for `target`.

    The ledger is append-only — duplicates can exist (refine-skill rewrites on
    re-runs). The latest entry wins. Returns None if no entry matches.
    """
    if not ledger_path.exists():
        return None
    target_norm = str(Path(target))
    latest: str | None = None
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        cols = line.split("\t")
        if len(cols) < 2 or not cols[0].strip():
            continue
        if str(Path(cols[0].strip())) == target_norm:
            latest = cols[1].strip()
    return latest


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

    On lock timeout (another bg worker holds the lock) this function returns
    silently WITHOUT touching the status file — the lock holder is keeping the
    file fresh and any write here would only flicker its in-progress phase.
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
        return


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

    # v0.3.11: track per-round OK/SKIP outcomes by inspecting what the
    # refine-skill wrote to the ledger after each `claude --print` call.
    # The wrapper used to claim `last_outcome=ok` whenever picked was
    # non-empty — even for the user-visible "3 notes · OK" line that
    # actually meant "3 SKIPs · 0 notes".
    ok_count = 0
    skip_count = 0

    for i, jsonl in enumerate(picked, start=1):
        backlog = compute_backlog(projects_dir, ledger_path)
        write_status(
            vault, "refining", i, total, backlog, reminder_active, started_at,
            last_ok=ok_count, last_skip=skip_count,
        )
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
        outcome = _latest_outcome_for_path(ledger_path, jsonl)
        if outcome == "OK":
            ok_count += 1
        elif outcome == "SKIP":
            skip_count += 1
        # Other outcomes (None / unknown status) are not counted — they remain
        # invisible to the user, which is correct: an absent ledger row means
        # the skill didn't reach a decision (crash, timeout) and nothing was
        # added to the vault.

    if picked:
        backlog = compute_backlog(projects_dir, ledger_path)
        write_status(
            vault, "mining", total, total, backlog, reminder_active, started_at,
            last_ok=ok_count, last_skip=skip_count,
        )
        sessions_dir = Path(vault) / "Sessions"
        rc = runner([sys.executable, "-m", "mnemos.cli", "--vault", str(vault), "mine", str(sessions_dir)])
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"  mine exit={rc}\n")

    if reminder_active:
        state = pending_load(vault)
        state.backlog_reminder_last_shown = datetime.now(timezone.utc).isoformat(timespec="seconds")
        pending_save(vault, state)

    backlog = compute_backlog(projects_dir, ledger_path)
    finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if not picked:
        outcome = "noop"
    elif ok_count > 0:
        outcome = "ok"
    else:
        outcome = "skip"
    write_status(
        vault, "idle", total, total, backlog, False, started_at,
        last_outcome=outcome,
        last_finished_at=finished_at,
        last_ok=ok_count if picked else None,
        last_skip=skip_count if picked else None,
    )
