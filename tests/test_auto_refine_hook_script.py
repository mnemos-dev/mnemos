"""Tests for `mnemos.auto_refine_hook` module CLI arg handling + SessionStart filtering.

After v0.3.0a the hook is a proper package module invoked as
`python -m mnemos.auto_refine_hook --vault <path>` (no filesystem path
to a script directory — that path didn't exist for pip-installed users).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _run_hook(tmp_path: Path, stdin: str, projects_jsonls: int = 0) -> subprocess.CompletedProcess:
    """Invoke the wrapper with an isolated HOME pointing inside tmp_path.

    `projects_jsonls` seeds N transcripts under <home>/.claude/projects/proj/.
    """
    home = tmp_path / "home"
    projects = home / ".claude" / "projects" / "proj"
    projects.mkdir(parents=True, exist_ok=True)
    for i in range(projects_jsonls):
        (projects / f"session-{i}.jsonl").write_text("{}\n", encoding="utf-8")

    env = {k: v for k, v in os.environ.items() if k != "MNEMOS_VAULT"}
    env["USERPROFILE"] = str(home)  # Windows
    env["HOME"] = str(home)         # POSIX

    return subprocess.run(
        [sys.executable, "-m", "mnemos.auto_refine_hook", "--vault", str(tmp_path)],
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


# ---------------------------------------------------------------------------
# v0.3 task 3.7d — source filter (skip mid-conversation events) + self-exclude
# ---------------------------------------------------------------------------


def test_hook_script_skips_compact_source(tmp_path):
    """source=compact fires on auto-compaction mid-conversation — wrapper must no-op."""
    payload = json.dumps({
        "session_id": "abc",
        "transcript_path": str(tmp_path / "proj" / "sess" / "main.jsonl"),
        "hook_event_name": "SessionStart",
        "source": "compact",
    })
    # Even with picks available, the source filter must short-circuit.
    result = _run_hook(tmp_path, stdin=payload, projects_jsonls=2)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert not (tmp_path / ".mnemos-hook-status.json").exists(), \
        "compact-source SessionStart must not touch the status file"


def test_hook_script_skips_unknown_source(tmp_path):
    """Unknown sources must default-skip (forward-compat: don't run on new event types we haven't vetted)."""
    payload = json.dumps({
        "session_id": "abc",
        "transcript_path": str(tmp_path / "proj" / "sess" / "main.jsonl"),
        "hook_event_name": "SessionStart",
        "source": "future-event-we-do-not-know",
    })
    result = _run_hook(tmp_path, stdin=payload, projects_jsonls=2)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert not (tmp_path / ".mnemos-hook-status.json").exists()


def test_hook_script_runs_on_resume_source(tmp_path):
    """source=resume is a legitimate fresh-session event — wrapper must run normally."""
    payload = json.dumps({
        "session_id": "abc",
        "transcript_path": str(tmp_path / "proj" / "sess" / "main.jsonl"),
        "hook_event_name": "SessionStart",
        "source": "resume",
    })
    result = _run_hook(tmp_path, stdin=payload, projects_jsonls=1)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert (tmp_path / ".mnemos-hook-status.json").exists()


def test_hook_script_runs_on_clear_source(tmp_path):
    """source=clear (after /clear) is a legitimate fresh-context event."""
    payload = json.dumps({
        "session_id": "abc",
        "transcript_path": str(tmp_path / "proj" / "sess" / "main.jsonl"),
        "hook_event_name": "SessionStart",
        "source": "clear",
    })
    result = _run_hook(tmp_path, stdin=payload, projects_jsonls=1)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert (tmp_path / ".mnemos-hook-status.json").exists()


def test_hook_script_excludes_self_transcript_from_picks(tmp_path):
    """The current session's own transcript must NOT end up in the picked-for-refine list.

    Without this, the in-progress conversation's JSONL would be refined while the user
    is still adding turns — the second half of the conversation would be silently lost
    because the ledger marks the file as already-OK.
    """
    # Seed three JSONLs and pick the newest as the "current" session transcript.
    home = tmp_path / "home"
    projects_dir = home / ".claude" / "projects" / "proj"
    projects_dir.mkdir(parents=True)
    paths = []
    for i, mtime in enumerate([1_000_000, 2_000_000, 3_000_000]):
        p = projects_dir / f"session-{i}.jsonl"
        p.write_text("{}\n", encoding="utf-8")
        os.utime(p, (mtime, mtime))
        paths.append(p)
    self_transcript = paths[2]  # newest = current session

    env = {k: v for k, v in os.environ.items() if k != "MNEMOS_VAULT"}
    env["USERPROFILE"] = str(home)
    env["HOME"] = str(home)
    payload = json.dumps({
        "session_id": "abc",
        "transcript_path": str(self_transcript),
        "hook_event_name": "SessionStart",
        "source": "startup",
    })
    result = subprocess.run(
        [sys.executable, "-m", "mnemos.auto_refine_hook", "--vault", str(tmp_path)],
        input=payload, capture_output=True, text=True, timeout=15, env=env,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads((tmp_path / ".mnemos-hook-status.json").read_text(encoding="utf-8"))
    # total == 2 means the picker dropped the self-transcript and only picked the other two.
    assert data["total"] == 2, \
        f"self-transcript must be excluded from picks; got total={data['total']!r}"
