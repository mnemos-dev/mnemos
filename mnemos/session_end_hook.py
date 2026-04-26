"""SessionEnd hook + detached worker pipeline.

Hook mode (default): reads Claude Code's SessionEnd JSON from stdin, validates,
and spawns a detached worker via CREATE_BREAKAWAY_FROM_JOB so the worker
survives Claude Code termination (X-close, /exit). Hook returns under 100 ms
to fit Claude Code's 5-second SessionEnd grace window.

Worker mode (``--worker``): runs the 3-stage pipeline sequentially —
refine THIS transcript -> regen briefing cache -> conditionally fire
identity refresh. Each stage is independent: a failure in one continues
into the next so partial progress is preserved.

All LLM work flows through ``claude --print`` subscription quota; the
ANTHROPIC_API_KEY is stripped from the child env so we never accidentally
burn API credits.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

HOOK_ACTIVE_ENV = "MNEMOS_RECALL_HOOK_ACTIVE"
WORKER_LOCK = ".mnemos-end-worker.flock"


@dataclass
class SessionEndInput:
    session_id: str
    transcript_path: str
    cwd: str


def parse_input(raw: str) -> SessionEndInput:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return SessionEndInput(
        session_id=str(data.get("session_id", "")),
        transcript_path=str(data.get("transcript_path", "")),
        cwd=str(data.get("cwd", "")),
    )


def _argv_value(argv: list[str], flag: str) -> str | None:
    """Pull `--flag value` out of argv. Returns None if missing or terminal."""
    if flag in argv:
        idx = argv.index(flag)
        if idx + 1 < len(argv):
            return argv[idx + 1]
    return None


def _resolve_vault(argv: list[str] | None = None) -> Path | None:
    """Vault discovery order: --vault arg, MNEMOS_VAULT env, mnemos.yaml walk."""
    if argv:
        explicit = _argv_value(argv, "--vault")
        if explicit:
            p = Path(explicit)
            if p.exists():
                return p
    v = os.environ.get("MNEMOS_VAULT")
    if v:
        p = Path(v)
        if p.exists():
            return p
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if (parent / "mnemos.yaml").exists():
            return parent
    return None


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    # --worker mode bypasses every hook-side guard so the detached worker
    # spawned by the hook can do the real work even when HOOK_ACTIVE_ENV
    # is set (it inherits the env from the hook invocation).
    if "--worker" in argv:
        return worker_main(argv)

    # Hook mode re-entry guard
    if os.environ.get(HOOK_ACTIVE_ENV):
        return 0

    try:
        raw = sys.stdin.read()
    except Exception:
        return 0

    inp = parse_input(raw)
    vault = _resolve_vault(argv)
    if vault is None:
        return 0

    from mnemos.recall_briefing import read_recall_mode
    if read_recall_mode(vault) != "skill":
        return 0

    # Pre-validate transcript before spawning anything heavyweight
    if not inp.transcript_path:
        return 0
    transcript = Path(inp.transcript_path)
    if not transcript.exists():
        return 0

    # TODO Task 7.2: spawn detached worker with breakaway flag
    return 0


def worker_main(argv: list[str]) -> int:
    """Worker entry — placeholder until Task 7.3."""
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
