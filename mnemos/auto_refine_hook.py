#!/usr/bin/env python3
"""SessionStart hook wrapper — synchronous <1s, then detach.

Claude Code calls this script. It:
  1. Resolves the vault (--vault flag, else MNEMOS_VAULT env, else no-op)
  2. Reads optional SessionStart JSON from stdin; skips subagent invocations
     (transcript_path under /subagents/) so agent-heavy workflows don't spawn
     a fresh bg worker on every dispatch.
  3. Computes picked JSONLs, backlog, reminder decision
  4. If there's nothing to do (no picks AND no reminder) → exits 0 silently
     so empty SessionStart events don't write a flicker-causing status row.
  5. Otherwise writes the initial statusline state (phase=refining, current=0
     when there's work; skipped entirely for the reminder-only path)
  6. Emits hook JSON with `additionalContext` (if reminder active)
  7. Spawns detached `python -m mnemos.auto_refine_background` subprocess
  8. Exits 0
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _find_vault(argv: list[str]) -> Path | None:
    # --vault <path> takes precedence
    if "--vault" in argv:
        idx = argv.index("--vault")
        if idx + 1 < len(argv):
            return Path(argv[idx + 1])
    env = os.environ.get("MNEMOS_VAULT")
    if env:
        return Path(env)
    return None


def _read_hook_input() -> dict:
    """Best-effort read of Claude Code's SessionStart JSON from stdin.

    Returns {} on any failure (empty stdin, non-JSON, missing fields). Callers
    must tolerate missing keys — the wrapper always continues with sensible
    defaults so older Claude Code versions that don't pipe JSON still work.
    """
    if sys.stdin is None or sys.stdin.isatty():
        return {}
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, ValueError):
        return {}


def _is_subagent_event(hook_input: dict) -> bool:
    """True if this SessionStart fired for a subagent (not the primary session).

    Claude Code stores subagent transcripts under
    `<project>/<session>/subagents/agent-*.jsonl`. The presence of a `subagents`
    path component in `transcript_path` is the canonical marker.
    """
    transcript_path = hook_input.get("transcript_path") or ""
    if not transcript_path:
        return False
    norm = transcript_path.replace("\\", "/")
    return "/subagents/" in norm


# SessionStart `source` whitelist — only these are treated as "fresh-session"
# events worth running auto-refine for. `compact` (auto-compaction) fires
# mid-conversation while the transcript is still being written and would cause
# the picker to refine an in-progress JSONL, silently losing later content.
# Empty string is allowed for backward compat with older Claude Code releases
# that didn't pipe a `source` field. Unknown future sources default-skip so a
# new event type doesn't trigger unintended refines until we vet it.
_FRESH_SESSION_SOURCES = {"", "startup", "resume", "clear"}


def _is_fresh_session_source(hook_input: dict) -> bool:
    source = hook_input.get("source") or ""
    return source in _FRESH_SESSION_SOURCES


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    vault = _find_vault(sys.argv[1:])
    if vault is None or not vault.exists():
        return 0

    hook_input = _read_hook_input()
    if _is_subagent_event(hook_input):
        # Subagent dispatches don't need their own auto-refine round; skip
        # entirely so the primary session's bg worker stays uncontested.
        return 0

    if not _is_fresh_session_source(hook_input):
        # Mid-conversation events (`compact`) and unknown future event types
        # don't represent the user starting fresh; refining now would lock the
        # in-progress transcript into the ledger before it's actually finished.
        return 0

    try:
        from mnemos.auto_refine import (
            ACTIVE_SESSIONS_DIR,
            compute_backlog,
            get_active_transcript_paths,
            pick_recent_jsonls,
            read_status_phase,
            register_active_session,
            resolve_ledger_path,
            should_show_reminder,
            write_status,
        )
        from mnemos.pending import load as pending_load
    except ModuleNotFoundError:
        return 0

    projects_dir = Path.home() / ".claude" / "projects"
    ledger = resolve_ledger_path()

    # v0.3.12: register this session + discover all active sessions so the
    # picker never touches a transcript that's still being written.
    sessions_dir = projects_dir / ACTIVE_SESSIONS_DIR
    self_transcript = hook_input.get("transcript_path") or ""
    session_id = hook_input.get("session_id") or ""
    if session_id and self_transcript:
        register_active_session(sessions_dir, session_id, self_transcript, os.getppid())
    active_paths = get_active_transcript_paths(sessions_dir)
    # Merge self-transcript (may lack session_id in older Claude Code versions)
    if self_transcript:
        active_paths.add(self_transcript)

    picked = pick_recent_jsonls(projects_dir, ledger, n=3, exclude=active_paths)
    backlog = compute_backlog(projects_dir, ledger, active_paths=active_paths)

    today = datetime.now(timezone.utc)
    state = pending_load(vault)
    reminder = should_show_reminder(state, today, backlog)

    # Nothing to refine and no reminder → don't touch the status file.
    if not picked and not reminder:
        return 0

    started_at = today.isoformat(timespec="seconds")
    if picked:
        # Only write initial status if no other bg worker is actively running.
        # Without this guard, a second session's wrapper overwrites the first
        # worker's in-progress "refining 2/3" with a stale "refining 0/3" that
        # never updates (the second bg worker exits on lock timeout). v0.3.12b.
        current_phase = read_status_phase(vault)
        if current_phase not in ("refining", "mining"):
            write_status(
                vault=vault,
                phase="refining",
                current=0,
                total=len(picked),
                backlog=backlog,
                reminder_active=reminder,
                started_at=started_at,
            )

    if reminder:
        msg = (
            f"Mnemos auto-refine started: {len(picked)} recent Claude Code "
            f"sessions being refined in background. Backlog: {backlog} older "
            f"transcripts not yet processed — run /mnemos-refine-transcripts "
            f"to catch up whenever you want."
        )
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": msg,
            }
        }))

    picked_args = [str(p) for p in picked]
    bg_cmd = [
        sys.executable, "-m", "mnemos.auto_refine_background",
        "--vault", str(vault),
        "--projects-dir", str(projects_dir),
        "--ledger", str(ledger),
        "--started-at", started_at,
        "--reminder-active", "1" if reminder else "0",
        "--picked", *picked_args,
    ]

    kwargs: dict = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        DETACHED_PROCESS = 0x00000008
        CREATE_NO_WINDOW = 0x08000000
        kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True

    try:
        subprocess.Popen(bg_cmd, **kwargs)
    except FileNotFoundError:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
