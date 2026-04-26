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
