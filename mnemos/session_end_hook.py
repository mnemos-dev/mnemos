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


def _child_env() -> dict:
    """Build the env passed to the detached worker.

    Strips ANTHROPIC_API_KEY so the worker's `claude --print` invocations
    fall through to the user's Claude Code subscription quota. Sets the
    HOOK_ACTIVE_ENV marker so any nested SessionStart hook fired inside
    the worker's child claude processes short-circuits cleanly instead of
    re-entering this module.
    """
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    env[HOOK_ACTIVE_ENV] = "1"
    return env


def _spawn_detached_worker(transcript: str, cwd: str, vault: Path) -> None:
    """Spawn the worker pipeline as a detached process.

    Windows: combine DETACHED_PROCESS + CREATE_NEW_PROCESS_GROUP +
    CREATE_BREAKAWAY_FROM_JOB so the worker outlives the Claude Code
    process that spawned it (X-close survival). If the parent job
    object refuses breakaway (rare), retry without that flag — partial
    survival is better than nothing.

    POSIX: start_new_session=True is enough.
    """
    cmd = [
        sys.executable, "-m", "mnemos.session_end_hook", "--worker",
        "--transcript", transcript,
        "--cwd", cwd,
        "--vault", str(vault),
    ]
    base_kwargs: dict = {
        "env": _child_env(),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        CREATE_BREAKAWAY_FROM_JOB = 0x01000000
        try:
            subprocess.Popen(
                cmd,
                creationflags=(
                    DETACHED_PROCESS
                    | CREATE_NEW_PROCESS_GROUP
                    | CREATE_BREAKAWAY_FROM_JOB
                ),
                **base_kwargs,
            )
            return
        except OSError:
            try:
                subprocess.Popen(
                    cmd,
                    creationflags=(DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP),
                    **base_kwargs,
                )
            except OSError:
                pass
    else:
        try:
            subprocess.Popen(cmd, start_new_session=True, **base_kwargs)
        except OSError:
            pass


def _user_settings_path() -> Path:
    return Path.home() / ".claude" / "settings.json"


def _detect_stale_hook_signature(managed_by: str) -> bool:
    """Return True iff settings.json has a SessionEnd entry with the given
    ``_managed_by`` whose ``_version`` is not ``v1.1``."""
    settings_path = _user_settings_path()
    if not settings_path.exists():
        return False
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    for entry in data.get("hooks", {}).get("SessionEnd", []):
        if entry.get("_managed_by") == managed_by:
            return entry.get("_version") != "v1.1"
    return False


def build_hook_entry(vault: str) -> dict:
    """Schema for the SessionEnd entry written into ~/.claude/settings.json
    by ``mnemos install-end-hook --v1`` (Task 8.1).
    """
    return {
        "matcher": "*",
        "_managed_by": "mnemos-session-end",
        "_version": "v1.1",
        "hooks": [
            {
                "type": "command",
                "command": f'python -m mnemos.session_end_hook --vault "{vault}"',
                "timeout": 5000,
            }
        ],
    }


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

    # v1.1 stale-hook guard: if our own settings.json entry is from a prior
    # version (or missing _version), print guidance to stderr and exit 0
    # so the SessionEnd event still completes cleanly.
    if _detect_stale_hook_signature("mnemos-session-end"):
        print(
            "Mnemos v1.1 detected an outdated SessionEnd hook entry.\n"
            "Run `mnemos install-end-hook --v1` to update.",
            file=sys.stderr,
        )
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

    if not inp.transcript_path:
        return 0
    transcript = Path(inp.transcript_path)
    if not transcript.exists():
        return 0

    _spawn_detached_worker(str(transcript), inp.cwd, vault)
    return 0


def _parse_worker_args(argv: list[str]):
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--worker", action="store_true")
    p.add_argument("--transcript", default="")
    p.add_argument("--cwd", default="")
    p.add_argument("--vault", default="")
    ns, _ = p.parse_known_args(argv)
    return ns


def _run_refine(transcript: str) -> None:
    """Sync refine via /mnemos-refine-transcripts skill subprocess."""
    cmd = [
        "claude", "--print", "--dangerously-skip-permissions",
        "--model", "sonnet",
        f"/mnemos-refine-transcripts {transcript}",
    ]
    subprocess.call(
        cmd,
        env=_child_env(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _run_brief_regen(cwd: str) -> None:
    """Sync brief regen via /mnemos-briefing skill subprocess."""
    cmd = [
        "claude", "--print", "--dangerously-skip-permissions",
        "--model", "sonnet",
        f"/mnemos-briefing {cwd}",
    ]
    subprocess.call(
        cmd,
        env=_child_env(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _run_identity_refresh_if_due(vault: Path) -> None:
    """Fire /mnemos-identity-refresh when delta + min-days gates both pass."""
    from mnemos.config import load_config
    cfg = load_config(str(vault))
    if not cfg.identity.auto_refresh:
        return

    identity_path = vault / "_identity" / "L0-identity.md"
    if not identity_path.exists():
        return  # Identity not bootstrapped — refresh has nothing to update

    text = identity_path.read_text(encoding="utf-8", errors="replace")
    import re
    m = re.search(r"session_count_at_refresh:\s*(\d+)", text)
    last_count = int(m.group(1)) if m else 0
    sessions_dir = vault / "Sessions"
    current_count = (
        sum(1 for _ in sessions_dir.glob("*.md")) if sessions_dir.exists() else 0
    )
    delta = current_count - last_count
    if delta < cfg.identity.refresh_session_delta:
        return

    m_lr = re.search(r"last_refreshed:\s*(\S+)", text)
    if m_lr:
        from datetime import datetime, timezone
        try:
            last_refreshed = datetime.fromisoformat(
                m_lr.group(1).replace("Z", "+00:00")
            )
            elapsed_days = (
                (datetime.now(timezone.utc) - last_refreshed).total_seconds() / 86400
            )
            if elapsed_days < cfg.identity.refresh_min_days:
                return
        except (ValueError, TypeError):
            pass  # Malformed timestamp — proceed; better to refresh than skip

    cmd = [
        "claude", "--print", "--dangerously-skip-permissions",
        "--model", "sonnet",
        "/mnemos-identity-refresh",
    ]
    subprocess.call(
        cmd,
        env=_child_env(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def worker_main(argv: list[str]) -> int:
    """3-stage sequential pipeline: refine -> brief regen -> identity refresh.

    Each stage is wrapped in its own try/except: a failure in one continues
    into the next so partial progress is preserved (e.g. brief regen still
    fires even if refine failed).
    """
    ns = _parse_worker_args(argv)
    if not ns.transcript or not ns.cwd or not ns.vault:
        return 0
    vault = Path(ns.vault)
    if not vault.exists():
        return 0

    # Best-effort flock so two SessionEnd workers (e.g. simultaneous /exit
    # and X-close) don't pile up on the same vault.
    lock = None
    try:
        import filelock
        lock = filelock.FileLock(str(vault / WORKER_LOCK), timeout=0.1)
        try:
            lock.acquire(timeout=0.1)
        except filelock.Timeout:
            return 0
    except ImportError:
        lock = None

    try:
        try:
            _run_refine(ns.transcript)
        except Exception:
            pass
        try:
            _run_brief_regen(ns.cwd)
        except Exception:
            pass
        try:
            _run_identity_refresh_if_due(vault)
        except Exception:
            pass
    finally:
        if lock is not None:
            try:
                lock.release()
            except Exception:
                pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
