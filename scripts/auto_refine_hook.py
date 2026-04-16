#!/usr/bin/env python3
"""SessionStart hook wrapper — synchronous <1s, then detach.

Claude Code calls this script. It:
  1. Resolves the vault (env MNEMOS_VAULT, else no-op)
  2. Computes picked JSONLs, backlog, reminder decision
  3. Writes initial statusline state
  4. Emits hook JSON with `additionalContext` (if reminder active)
  5. Spawns detached `python -m mnemos.auto_refine_background` subprocess
  6. Exits 0
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


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    vault = _find_vault(sys.argv[1:])
    if vault is None or not vault.exists():
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

    started_at = today.isoformat(timespec="seconds")
    write_status(
        vault=vault,
        phase="starting",
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
