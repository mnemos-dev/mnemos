"""Auto-refine hook: SessionStart orchestration for last-3 JSONL refinement."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
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
ACTIVE_SESSIONS_DIR = ".mnemos-active-sessions"
ACTIVE_SESSION_MAX_AGE_SECONDS = 86400
# mtime fallback for sessions started before 3.12 (no PID marker).
# If a JSONL was modified within this window AND has no marker, assume it's
# still being written to. 30 min is generous: most sessions either get a
# marker on their first hook fire or are closed within minutes.
RECENTLY_MODIFIED_SECONDS = 1800

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


# ---------------------------------------------------------------------------
# Active-session tracking (v0.3 task 3.12)
# ---------------------------------------------------------------------------


def _is_pid_alive(pid: int) -> bool:
    """Return True if a process with `pid` is currently running."""
    if os.name == "nt":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid,
        )
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def register_active_session(
    sessions_dir: Path,
    session_id: str,
    transcript_path: str,
    pid: int,
) -> Path:
    """Write a marker file so other hooks know this session is alive."""
    sessions_dir.mkdir(parents=True, exist_ok=True)
    marker = sessions_dir / f"{session_id}.json"
    marker.write_text(
        json.dumps({
            "pid": pid,
            "transcript_path": transcript_path,
            "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }),
        encoding="utf-8",
    )
    return marker


def get_active_transcript_paths(sessions_dir: Path) -> set[str]:
    """Return transcript paths of currently-running sessions.

    Scans marker files under `sessions_dir`, checks each PID for liveness,
    and cleans up stale/dead markers. Markers older than 24 h are removed
    regardless of PID (guards against PID recycling on long-lived machines).
    """
    if not sessions_dir.exists():
        return set()

    now = datetime.now(timezone.utc)
    active: set[str] = set()
    for marker in list(sessions_dir.glob("*.json")):
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            marker.unlink(missing_ok=True)
            continue
        pid = data.get("pid", 0)
        transcript = data.get("transcript_path", "")
        started_at = data.get("started_at", "")
        if started_at:
            try:
                ts = datetime.fromisoformat(started_at)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if (now - ts).total_seconds() > ACTIVE_SESSION_MAX_AGE_SECONDS:
                    marker.unlink(missing_ok=True)
                    continue
            except (ValueError, TypeError):
                pass
        if pid and _is_pid_alive(pid) and transcript:
            active.add(transcript)
        else:
            marker.unlink(missing_ok=True)
    return active


def _is_recently_modified(path: Path, threshold: int = RECENTLY_MODIFIED_SECONDS) -> bool:
    """True if `path` was modified within the last `threshold` seconds."""
    try:
        return (time.time() - path.stat().st_mtime) < threshold
    except OSError:
        return False


def read_status_phase(vault: Path) -> str | None:
    """Return the current `phase` from the statusline JSON, or None."""
    path = Path(vault) / STATUS_FILENAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("phase")
    except (json.JSONDecodeError, OSError):
        return None


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
        # mtime fallback (v0.3.12b): unmarked JSONL with recent mtime is
        # likely an active session that predates PID markers. Skip it.
        if _is_recently_modified(candidate):
            continue
        picked.append(candidate)
        if len(picked) >= n:
            break
    return picked


def _pick_unprocessed_jsonls(
    projects_dir: Path,
    ledger_path: Path,
    limit: int,
    exclude: set[str] | None = None,
    active_paths: set[str] | None = None,
    min_user_turns: int = MIN_USER_TURNS,
) -> list[Path]:
    """Return up to `limit` most-recent unprocessed JSONLs (skill-mine picker).

    Same filtering rules as ``pick_recent_jsonls`` (subagent skip, ledger skip,
    exclude, min_user_turns, recently-modified skip) but with an explicit
    ``limit`` instead of the hard-coded n=3. Used by the skill-mine pipeline
    which may process up to `cap` sources per fire (Spec §4.2).
    """
    if not projects_dir.exists() or limit <= 0:
        return []

    ledger_paths = _read_ledger_paths(ledger_path)
    excluded = {str(Path(p)) for p in (exclude or set())}
    excluded |= {str(Path(p)) for p in (active_paths or set())}
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
        if _is_recently_modified(candidate):
            continue
        picked.append(candidate)
        if len(picked) >= limit:
            break
    return picked


def _pick_unmined_sessions(
    vault: Path,
    mine_ledger_path: Path,
    palace_root: Path,
    limit: int,
) -> list[Path]:
    """Return up to `limit` Sessions/*.md files NOT recorded as OK in the
    skill-mine ledger for this palace.

    The mine-llm ledger format (skills/mnemos-mine-llm/SKILL.md §4) is:
        <input-abs-path>\\t<palace-root>\\t<drawer-count>\\t<ISO-ts|SKIP:reason>

    A session counts as "mined" iff the ledger has a row where:
    - column 0 == session path
    - column 1 == palace_root (same palace — different palaces retry)
    - column 3 is an ISO timestamp (matches r'^\\d{4}-\\d{2}-\\d{2}T').
    SKIP and ERROR rows re-queue (user may want to retry).
    """
    import re

    sessions_dir = Path(vault) / "Sessions"
    if not sessions_dir.exists() or limit <= 0:
        return []

    palace_str = str(Path(palace_root))
    ok_paths: set[str] = set()
    if mine_ledger_path.exists():
        ts_re = re.compile(r"^\d{4}-\d{2}-\d{2}T")
        for line in mine_ledger_path.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            if str(Path(parts[1])) != palace_str:
                continue
            if ts_re.match(parts[3]):
                ok_paths.add(str(Path(parts[0])))

    candidates = sorted(
        sessions_dir.glob("*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    picked: list[Path] = []
    for c in candidates:
        if str(c) in ok_paths:
            continue
        picked.append(c)
        if len(picked) >= limit:
            break
    return picked


def compute_backlog(
    projects_dir: Path,
    ledger_path: Path,
    min_user_turns: int = MIN_USER_TURNS,
    active_paths: set[str] | None = None,
) -> int:
    """Count JSONLs under `projects_dir` that are not listed in the ledger.

    Uses the same path normalisation as `pick_recent_jsonls` so counts stay
    consistent between the picker and the backlog reminder. Same v0.3.11
    `min_user_turns` filter applies — backlog reflects *processable* work, not
    every JSONL sitting on disk. `active_paths` (v0.3.12) further excludes
    transcripts that belong to currently-running sessions — they aren't
    available to process yet so counting them would be misleading.
    """
    if not projects_dir.exists():
        return 0

    ledger_paths = _read_ledger_paths(ledger_path)
    excluded = {str(Path(p)) for p in (active_paths or set())}
    total = 0
    for candidate in projects_dir.rglob("*.jsonl"):
        if _is_subagent_jsonl(candidate):
            continue
        key = str(candidate)
        if key in ledger_paths or key in excluded:
            continue
        if min_user_turns > 0 and _count_user_turns(candidate) < min_user_turns:
            continue
        if _is_recently_modified(candidate):
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
    triggering_session_id: str | None = None,
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
    if triggering_session_id:
        payload["triggering_session_id"] = triggering_session_id

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


def _latest_session_for_jsonl(
    ledger_path: Path, jsonl: Path, vault: Path,
) -> tuple[str, Path] | None:
    """Return (outcome, session_md_abs_path) for the latest ledger row matching `jsonl`.

    Refine ledger format is ``<jsonl>\\t<outcome>\\t<session_md_name>`` where
    ``session_md_name`` is Sessions/-relative. Returns None if no row matches.
    Column 3 may be absent on ERROR rows — in that case we return (outcome, None)
    by collapsing the tuple to None (caller falls back to Sessions/ newest file).
    """
    if not ledger_path.exists():
        return None
    target = str(Path(jsonl))
    latest: tuple[str, Path] | None = None
    for line in ledger_path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        if str(Path(parts[0])) != target:
            continue
        session_md = Path(vault) / "Sessions" / parts[2]
        latest = (parts[1], session_md)
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


def _read_mine_mode(vault: Path) -> str:
    """Return ``mine_mode`` from ``<vault>/mnemos.yaml``; default ``script``.

    Why: the hook's regex ``mnemos mine`` call must not clobber a skill-mined
    palace. When a user has accepted a skill-mine batch, ``mnemos.yaml`` flips
    to ``mine_mode: skill`` — after that, mining happens via the pilot
    orchestrator, not this hook. We read the yaml directly (no PyYAML dep) to
    keep the hook's import surface minimal.
    """
    yaml_path = Path(vault) / "mnemos.yaml"
    if not yaml_path.exists():
        return "script"
    try:
        text = yaml_path.read_text(encoding="utf-8")
    except OSError:
        return "script"
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("mine_mode:"):
            return s.split(":", 1)[1].strip().strip("'\"")
    return "script"


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
    triggering_session_id: str = "",
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
                triggering_session_id=triggering_session_id,
            )
    except Timeout:
        return


def _run_skill_pipeline(
    *,
    vault: Path,
    projects_dir: Path,
    refine_ledger_path: Path,
    mine_ledger_path: Path,
    runner: Runner,
    cap: int = 10,
    active_paths: set[str] | None = None,
    exclude: set[str] | None = None,
    triggering_session_id: str = "",
    on_phase: Callable[[str, int, int, Path], None] | None = None,
    status_context: dict | None = None,
) -> None:
    """Skill-mine pipeline (Spec §4.3): two phases, A+B total ≤ `cap`.

    Phase A: unmined Sessions → /mnemos-mine-llm (priority, refine already done).
    Phase B: unrefined JSONLs → /mnemos-refine-transcripts then /mnemos-mine-llm
    chain per source (worker is sequential within one source).

    `on_phase` is an optional progress callback invoked before each subprocess
    with (phase_label, current_index, total_in_phase, source_path). Used by
    catch-up for foreground progress bars.

    `status_context` optionally carries ``backlog`` / ``reminder_active`` /
    ``started_at`` so the pipeline can call ``write_status`` for hook
    statusline updates. When None (typical for catch-up), statusline writes
    are skipped — catch-up prints to stdout instead.
    """
    from mnemos import processing_log as plog

    palace_root = Path(vault) / "Mnemos"
    palace_root.mkdir(parents=True, exist_ok=True)

    log_path = Path(vault) / HOOK_LOG_FILENAME

    def _status(phase_label: str, current: int, total: int) -> None:
        if status_context is None:
            return
        write_status(
            vault, phase_label, current, total,
            status_context.get("backlog", 0),
            status_context.get("reminder_active", False),
            status_context.get("started_at", _now_iso()),
            triggering_session_id=triggering_session_id or None,
        )

    # Phase A
    unmined = _pick_unmined_sessions(
        vault=vault, mine_ledger_path=mine_ledger_path,
        palace_root=palace_root, limit=cap,
    )
    total_fire = len(unmined)  # will grow when Phase B sizes itself
    for i, session_md in enumerate(unmined, start=1):
        plog.upsert_row(vault, source_type="md", path=session_md,
                        mined_outcome="PENDING")
        _status("mining", i, total_fire)
        if on_phase:
            on_phase("A-mine", i, len(unmined), session_md)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"[{_now_iso()}] phase=A mine {session_md}\n")
        rc = runner([
            "claude", "--print", "--dangerously-skip-permissions",
            f"/mnemos-mine-llm {session_md} {palace_root}",
        ])
        outcome, drawer_count, tokens = _read_mine_outcome(
            mine_ledger_path, session_md, palace_root,
        )
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"  exit={rc}  drawers={drawer_count}\n")
        plog.upsert_row(
            vault, source_type="md", path=session_md,
            mined_at=_now_iso() if outcome == "OK" else None,
            mined_outcome=outcome,
            drawer_count=drawer_count, tokens=tokens,
        )

    # Phase B (capacity remaining)
    remaining = cap - len(unmined)
    if remaining <= 0:
        return

    unrefined = _pick_unprocessed_jsonls(
        projects_dir=projects_dir, ledger_path=refine_ledger_path,
        limit=remaining, exclude=exclude or set(),
        active_paths=active_paths or set(),
    )
    total_fire = len(unmined) + len(unrefined)
    for i, jsonl in enumerate(unrefined, start=1):
        # Fire position counts Phase A items first.
        fire_pos = len(unmined) + i
        plog.upsert_row(vault, source_type="jsonl", path=jsonl,
                        refine_outcome="PENDING")
        _status("refining", fire_pos, total_fire)
        if on_phase:
            on_phase("B-refine", i, len(unrefined), jsonl)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"[{_now_iso()}] phase=B refine {jsonl}\n")
        rc_r = runner([
            "claude", "--print", "--dangerously-skip-permissions",
            f"/mnemos-refine-transcripts {jsonl}",
        ])
        refine_result = _latest_session_for_jsonl(refine_ledger_path, jsonl, vault)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"  exit={rc_r}\n")
        if refine_result is None or refine_result[0] != "OK":
            outcome = refine_result[0] if refine_result else "ERROR"
            plog.upsert_row(vault, source_type="jsonl", path=jsonl,
                            refined_at=_now_iso() if outcome == "OK" else None,
                            refine_outcome=outcome)
            continue
        _ok, session_md = refine_result
        plog.upsert_row(vault, source_type="jsonl", path=jsonl,
                        refined_at=_now_iso(), refine_outcome="OK",
                        mined_outcome="PENDING")
        _status("mining", fire_pos, total_fire)
        if on_phase:
            on_phase("B-mine", i, len(unrefined), jsonl)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"[{_now_iso()}] phase=B mine {session_md}\n")
        rc_m = runner([
            "claude", "--print", "--dangerously-skip-permissions",
            f"/mnemos-mine-llm {session_md} {palace_root}",
        ])
        outcome, drawer_count, tokens = _read_mine_outcome(
            mine_ledger_path, session_md, palace_root,
        )
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"  exit={rc_m}  drawers={drawer_count}\n")
        plog.upsert_row(vault, source_type="jsonl", path=jsonl,
                        mined_at=_now_iso() if outcome == "OK" else None,
                        mined_outcome=outcome,
                        drawer_count=drawer_count, tokens=tokens)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_mine_outcome(
    mine_ledger_path: Path, session_md: Path, palace_root: Path,
) -> tuple[str, int, int]:
    """Read the latest mine-llm ledger row for (session_md, palace_root).

    Returns (outcome, drawer_count, tokens). outcome is "OK" if column 3 is an
    ISO timestamp, "SKIP" if column 3 starts with "SKIP:", else "ERROR".
    drawer_count from column 2; tokens is 0 (skill-mine ledger does not record
    token usage — tokens column in xlsx stays empty for now, reserved for a
    later skill upgrade).
    """
    import re

    if not mine_ledger_path.exists():
        return ("ERROR", 0, 0)
    palace_str = str(Path(palace_root))
    target = str(Path(session_md))
    latest: tuple[str, int, int] | None = None
    ts_re = re.compile(r"^\d{4}-\d{2}-\d{2}T")
    for line in mine_ledger_path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        if str(Path(parts[0])) != target or str(Path(parts[1])) != palace_str:
            continue
        try:
            drawers = int(parts[2])
        except ValueError:
            drawers = 0
        if ts_re.match(parts[3]):
            latest = ("OK", drawers, 0)
        elif parts[3].startswith("SKIP"):
            latest = ("SKIP", drawers, 0)
        else:
            latest = ("ERROR", drawers, 0)
    return latest if latest is not None else ("ERROR", 0, 0)


def _run_locked(
    *,
    vault: Path,
    projects_dir: Path,
    ledger_path: Path,
    picked: list[Path],
    reminder_active: bool,
    started_at: str,
    runner: Runner,
    triggering_session_id: str = "",
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
            triggering_session_id=triggering_session_id,
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
            triggering_session_id=triggering_session_id,
        )
        sessions_dir = Path(vault) / "Sessions"
        if _read_mine_mode(vault) == "skill":
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write("  mine skipped (mine_mode=skill)\n")
        else:
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
        triggering_session_id=triggering_session_id,
    )
