"""SessionEnd worker pipeline tests — 3-stage sequencing, isolation, lock."""
from __future__ import annotations

from pathlib import Path

import pytest


def test_worker_runs_three_stages_in_order(tmp_path, monkeypatch):
    from mnemos.session_end_hook import worker_main

    (tmp_path / "mnemos.yaml").write_text(
        "schema_version: 2\nrecall_mode: skill\n"
        "identity:\n  auto_refresh: true\n  refresh_session_delta: 1\n  refresh_min_days: 0\n",
        encoding="utf-8",
    )
    transcript = tmp_path / "fake.jsonl"
    transcript.write_text(
        '{"type":"user","message":{"role":"user","content":"hi"}}\n' * 5,
        encoding="utf-8",
    )

    call_order: list = []
    monkeypatch.setattr(
        "mnemos.session_end_hook._run_refine",
        lambda t: call_order.append(("refine", t)),
    )
    monkeypatch.setattr(
        "mnemos.session_end_hook._run_brief_regen",
        lambda c: call_order.append(("brief", c)),
    )
    monkeypatch.setattr(
        "mnemos.session_end_hook._run_identity_refresh_if_due",
        lambda v: call_order.append(("identity", v)),
    )

    rc = worker_main([
        "--worker",
        "--transcript", str(transcript),
        "--cwd", "C:/test",
        "--vault", str(tmp_path),
    ])
    assert rc == 0
    assert [c[0] for c in call_order] == ["refine", "brief", "identity"]


def test_worker_continues_after_refine_failure(tmp_path, monkeypatch):
    from mnemos.session_end_hook import worker_main

    (tmp_path / "mnemos.yaml").write_text(
        "schema_version: 2\nrecall_mode: skill\n", encoding="utf-8"
    )
    transcript = tmp_path / "fake.jsonl"
    transcript.write_text("x", encoding="utf-8")

    def boom_refine(t):
        raise RuntimeError("refine failed")

    brief_called: list = []
    monkeypatch.setattr("mnemos.session_end_hook._run_refine", boom_refine)
    monkeypatch.setattr(
        "mnemos.session_end_hook._run_brief_regen",
        lambda c: brief_called.append(c),
    )
    monkeypatch.setattr(
        "mnemos.session_end_hook._run_identity_refresh_if_due",
        lambda v: None,
    )

    rc = worker_main([
        "--worker", "--transcript", str(transcript),
        "--cwd", "C:/test", "--vault", str(tmp_path),
    ])
    assert rc == 0
    assert len(brief_called) == 1, "brief must continue even after refine fails"


def test_worker_returns_silently_when_required_args_missing(tmp_path):
    from mnemos.session_end_hook import worker_main

    rc = worker_main(["--worker"])
    assert rc == 0


def test_worker_returns_when_vault_missing(tmp_path, monkeypatch):
    """If --vault path doesn't exist, worker exits silently without firing stages."""
    from mnemos.session_end_hook import worker_main

    refine_called: list = []
    monkeypatch.setattr(
        "mnemos.session_end_hook._run_refine",
        lambda t: refine_called.append(t),
    )
    rc = worker_main([
        "--worker", "--transcript", "/x.jsonl",
        "--cwd", "C:/test", "--vault", str(tmp_path / "nope"),
    ])
    assert rc == 0
    assert refine_called == []
