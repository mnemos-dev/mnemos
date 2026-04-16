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

    try:
        from mnemos.auto_refine import (
            compute_backlog,
            pick_recent_jsonls,
            resolve_ledger_path,
            should_show_reminder,
            write_status,
        )
        from mnemos.pending import load as pending_load
    except ModuleNotFoundError:
        return 0

    projects_dir = Path.home() / ".claude" / "projects"
    ledger = resolve_ledger_path()
    picked = pick_recent_jsonls(projects_dir, ledger, n=3)
    backlog = compute_backlog(projects_dir, ledger)

    today = datetime.now(timezone.utc)
    state = pending_load(vault)
    reminder = should_show_reminder(state, today, backlog)

    # Nothing to refine and no reminder → don't touch the status file.
    if not picked and not reminder:
        return 0

    started_at = today.isoformat(timespec="seconds")
    if picked:
        # Skip the misleading 'starting' phase that briefly snapshot-renders
        # 'starting 0m1s' before the bg worker writes 'refining'. Write
        # 'refining current=0' synchronously so the user immediately sees
        # progress framing.
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
