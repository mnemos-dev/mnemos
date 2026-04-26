"""SessionEnd hook tests — entry, parse, mode gate, breakaway spawn, stale detect."""
from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

import pytest


def test_parse_input_extracts_fields():
    from mnemos.session_end_hook import parse_input

    raw = json.dumps({
        "session_id": "abc123",
        "transcript_path": "/x.jsonl",
        "cwd": "C:/test",
    })
    parsed = parse_input(raw)
    assert parsed.session_id == "abc123"
    assert parsed.transcript_path == "/x.jsonl"
    assert parsed.cwd == "C:/test"


def test_parse_input_handles_empty():
    from mnemos.session_end_hook import parse_input

    parsed = parse_input("")
    assert parsed.session_id == ""
    assert parsed.transcript_path == ""
    assert parsed.cwd == ""


def test_main_exits_silent_when_recall_mode_not_skill(tmp_path, monkeypatch, capsys):
    from mnemos.session_end_hook import main

    (tmp_path / "mnemos.yaml").write_text("recall_mode: script\n", encoding="utf-8")
    monkeypatch.setenv("MNEMOS_VAULT", str(tmp_path))
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO('{"session_id":"x","transcript_path":"/x","cwd":"C:/test"}'),
    )
    rc = main(["--vault", str(tmp_path)])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == ""


def test_main_spawns_worker_with_breakaway_flag(tmp_path, monkeypatch):
    """Hook spawns a detached worker via Popen — Windows: breakaway + detached
    + new process group flags must all be set so worker outlives Claude Code."""
    import mnemos.session_end_hook as seh

    (tmp_path / "mnemos.yaml").write_text("recall_mode: skill\n", encoding="utf-8")
    transcript = tmp_path / "live.jsonl"
    transcript.write_text("{}\n", encoding="utf-8")

    captured_calls: list = []

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            captured_calls.append((cmd, kwargs))

    monkeypatch.setattr("subprocess.Popen", FakePopen)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(json.dumps({
            "session_id": "x",
            "transcript_path": str(transcript),
            "cwd": "C:/test",
        })),
    )
    monkeypatch.setenv("MNEMOS_VAULT", str(tmp_path))

    rc = seh.main(["--vault", str(tmp_path)])
    assert rc == 0
    assert len(captured_calls) == 1
    cmd, kwargs = captured_calls[0]
    assert "--worker" in cmd
    assert "--transcript" in cmd
    assert str(transcript) in cmd
    if os.name == "nt":
        flags = kwargs.get("creationflags", 0)
        assert flags & 0x01000000, "CREATE_BREAKAWAY_FROM_JOB must be set"
        assert flags & 0x00000008, "DETACHED_PROCESS must be set"
        assert flags & 0x00000200, "CREATE_NEW_PROCESS_GROUP must be set"
    # Child env must strip API key + carry HOOK_ACTIVE_ENV
    env = kwargs.get("env", {})
    assert "ANTHROPIC_API_KEY" not in env
    assert env.get(seh.HOOK_ACTIVE_ENV) == "1"


def test_main_skips_when_transcript_missing(tmp_path, monkeypatch):
    """Hook must not spawn a worker if the transcript path doesn't exist."""
    import mnemos.session_end_hook as seh

    (tmp_path / "mnemos.yaml").write_text("recall_mode: skill\n", encoding="utf-8")
    spawn_calls: list = []
    monkeypatch.setattr(
        "mnemos.session_end_hook._spawn_detached_worker",
        lambda *a, **kw: spawn_calls.append(a),
    )
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(json.dumps({
            "session_id": "x",
            "transcript_path": str(tmp_path / "nonexistent.jsonl"),
            "cwd": "C:/test",
        })),
    )

    rc = seh.main(["--vault", str(tmp_path)])
    assert rc == 0
    assert spawn_calls == []
