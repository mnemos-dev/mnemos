"""Small tests for scripts/auto_refine_hook.py CLI arg handling + SessionStart filtering."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_hook(tmp_path: Path, stdin: str, projects_jsonls: int = 0) -> subprocess.CompletedProcess:
    """Invoke the wrapper with an isolated HOME pointing inside tmp_path.

    `projects_jsonls` seeds N transcripts under <home>/.claude/projects/proj/.
    """
    script = REPO_ROOT / "scripts" / "auto_refine_hook.py"

    home = tmp_path / "home"
    projects = home / ".claude" / "projects" / "proj"
    projects.mkdir(parents=True, exist_ok=True)
    for i in range(projects_jsonls):
        (projects / f"session-{i}.jsonl").write_text("{}\n", encoding="utf-8")

    env = {k: v for k, v in os.environ.items() if k != "MNEMOS_VAULT"}
    env["USERPROFILE"] = str(home)  # Windows
    env["HOME"] = str(home)         # POSIX

    return subprocess.run(
        [sys.executable, str(script), "--vault", str(tmp_path)],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )


def test_hook_script_accepts_vault_cli_arg(tmp_path):
    """Script must prefer --vault CLI arg over MNEMOS_VAULT env. Empty stdin allowed."""
    result = _run_hook(tmp_path, stdin="", projects_jsonls=0)
    assert result.returncode == 0, f"stderr: {result.stderr}"


def test_hook_script_skips_subagent_session(tmp_path):
    """Subagent SessionStart events (transcript_path under /subagents/) must no-op."""
    payload = json.dumps({
        "session_id": "abc",
        "transcript_path": str(tmp_path / "proj" / "sess" / "subagents" / "agent-x.jsonl"),
        "hook_event_name": "SessionStart",
        "source": "startup",
    })
    # Seed picked candidates — even with work available, the subagent filter must
    # short-circuit before any status write.
    result = _run_hook(tmp_path, stdin=payload, projects_jsonls=2)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert not (tmp_path / ".mnemos-hook-status.json").exists(), \
        "subagent SessionStart must not touch the status file"


def test_hook_script_skips_when_nothing_to_do(tmp_path):
    """No JSONLs to refine + no reminder → wrapper writes nothing (avoids needless flicker)."""
    payload = json.dumps({
        "session_id": "abc",
        "transcript_path": str(tmp_path / "proj" / "sess" / "main.jsonl"),
        "hook_event_name": "SessionStart",
        "source": "startup",
    })
    result = _run_hook(tmp_path, stdin=payload, projects_jsonls=0)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert not (tmp_path / ".mnemos-hook-status.json").exists(), \
        "no-op SessionStart must not touch the status file"


def test_hook_script_writes_refining_phase_when_picked(tmp_path):
    """When there's actual work to do, wrapper writes phase=refining (skipping 'starting')."""
    payload = json.dumps({
        "session_id": "abc",
        "transcript_path": str(tmp_path / "proj" / "sess" / "main.jsonl"),
        "hook_event_name": "SessionStart",
        "source": "startup",
    })
    result = _run_hook(tmp_path, stdin=payload, projects_jsonls=1)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    status_file = tmp_path / ".mnemos-hook-status.json"
    assert status_file.exists()
    data = json.loads(status_file.read_text(encoding="utf-8"))
    assert data["phase"] == "refining", \
        f"wrapper should skip 'starting' and write 'refining' directly; got {data['phase']!r}"
    assert data["current"] == 0
    assert data["total"] >= 1
