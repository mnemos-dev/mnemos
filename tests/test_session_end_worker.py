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
        lambda t, vault=None: call_order.append(("refine", t)),
    )
    monkeypatch.setattr(
        "mnemos.session_end_hook._run_brief_regen",
        lambda c, v: call_order.append(("brief", c)),
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

    def boom_refine(t, vault=None):
        raise RuntimeError("refine failed")

    brief_called: list = []
    monkeypatch.setattr("mnemos.session_end_hook._run_refine", boom_refine)
    monkeypatch.setattr(
        "mnemos.session_end_hook._run_brief_regen",
        lambda c, v: brief_called.append(c),
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


def test_worker_brief_regen_writes_cache_to_disk(tmp_path, monkeypatch):
    """Regression: SessionEnd's _run_brief_regen MUST persist the briefing
    to <vault>/.mnemos-briefings/<slug>.md.

    Pre-fix bug: subprocess.call(..., stdout=subprocess.DEVNULL) discarded
    the skill's stdout entirely. The cache was never updated by SessionEnd,
    so /exit always left the next session with stale (one-session-old)
    briefing — the bg catchup at the next SessionStart was the only path
    that ever wrote the cache.
    """
    from mnemos.session_end_hook import _run_brief_regen
    from mnemos.recall_briefing import (
        BriefResult,
        cache_path_for,
        cwd_to_slug,
        read_cache_body,
    )

    vault = tmp_path
    (vault / "mnemos.yaml").write_text(
        "schema_version: 2\nrecall_mode: skill\n", encoding="utf-8"
    )
    (vault / "Sessions").mkdir()

    cwd = "C:/test/proj"
    expected_body = "**Current State:** persisted by SessionEnd worker\n"

    def fake_run_brief_sync(_cwd, runner=None):
        return BriefResult(ok=True, body=expected_body)

    monkeypatch.setattr(
        "mnemos.recall_briefing.run_brief_sync", fake_run_brief_sync
    )

    _run_brief_regen(cwd, vault)

    cache = cache_path_for(vault, cwd_to_slug(cwd))
    assert cache.exists(), (
        "SessionEnd brief regen must persist to .mnemos-briefings/<slug>.md"
    )
    assert "persisted by SessionEnd worker" in read_cache_body(cache)


def test_worker_identity_refresh_persists_to_disk(tmp_path, monkeypatch):
    """Regression: SessionEnd's _run_identity_refresh_if_due MUST persist
    the refreshed profile to <vault>/_identity/L0-identity.md.

    Pre-fix bug: same DEVNULL pattern as brief_regen. Skill stdout was
    thrown away, the identity layer was never updated by SessionEnd.
    """
    from mnemos.session_end_hook import _run_identity_refresh_if_due

    vault = tmp_path
    (vault / "mnemos.yaml").write_text(
        "schema_version: 2\nrecall_mode: skill\n"
        "identity:\n  auto_refresh: true\n  refresh_session_delta: 1\n  refresh_min_days: 0\n",
        encoding="utf-8",
    )

    identity_dir = vault / "_identity"
    identity_dir.mkdir()
    identity_path = identity_dir / "L0-identity.md"
    identity_path.write_text(
        "---\n"
        "last_refreshed: 2020-01-01T00:00:00+00:00\n"
        "session_count_at_refresh: 0\n"
        "---\n# Old Profile\n",
        encoding="utf-8",
    )

    sessions_dir = vault / "Sessions"
    sessions_dir.mkdir()
    (sessions_dir / "2026-04-29-new.md").write_text(
        "---\ntags: [proj/NewProject]\n---\nbody\n", encoding="utf-8"
    )

    refreshed_body = (
        "---\n"
        "last_refreshed: 2026-04-29T10:00:00+00:00\n"
        "session_count_at_refresh: 1\n"
        "---\n# Updated Profile\n"
    )

    def fake_invoke(_prompt, model="sonnet"):
        return refreshed_body

    monkeypatch.setattr("mnemos.identity._invoke_claude_print", fake_invoke)

    _run_identity_refresh_if_due(vault)

    text = identity_path.read_text(encoding="utf-8")
    assert "# Updated Profile" in text, (
        "SessionEnd identity refresh must persist refreshed body to L0-identity.md"
    )
    assert "session_count_at_refresh: 1" in text
