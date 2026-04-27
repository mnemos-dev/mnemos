"""Tests for identity bootstrap eligibility gate (Task 3.3 / 3.4)."""
from pathlib import Path

import pytest

from mnemos.identity import IdentityError, bootstrap


def test_bootstrap_blocks_below_threshold(tmp_path: Path, monkeypatch):
    """Bootstrap raises IdentityError when readiness < threshold."""
    sessions = tmp_path / "Sessions"
    sessions.mkdir()
    (sessions / "2026-01-01-x.md").write_text(
        "---\ndate: 2026-01-01\n---\nbody\n", encoding="utf-8"
    )
    # Config threshold 50%, but we'll set up so eligible=10 refined=1 -> 10%
    (tmp_path / "mnemos.yaml").write_text(
        "schema_version: 2\nidentity:\n  bootstrap_threshold_pct: 50\n",
        encoding="utf-8",
    )
    # Mock projects to have 10 eligible JSONLs
    monkeypatch.setattr(
        "mnemos.identity._count_eligible_jsonls_for_bootstrap",
        lambda vault: 10,
    )

    with pytest.raises(IdentityError) as exc_info:
        bootstrap(tmp_path)
    assert "10.0%" in str(exc_info.value) or "10%" in str(exc_info.value)
    assert "50" in str(exc_info.value)


def test_bootstrap_allows_above_threshold(tmp_path: Path, monkeypatch):
    sessions = tmp_path / "Sessions"
    sessions.mkdir()
    for i in range(8):
        (sessions / f"2026-01-{i+1:02d}-x.md").write_text(
            f"---\ndate: 2026-01-{i+1:02d}\n---\nbody {i}\n", encoding="utf-8"
        )
    (tmp_path / "mnemos.yaml").write_text(
        "schema_version: 2\nidentity:\n  bootstrap_threshold_pct: 25\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "mnemos.identity._count_eligible_jsonls_for_bootstrap",
        lambda vault: 10,
    )
    # Mock the actual LLM call so we don't burn quota in test
    monkeypatch.setattr(
        "mnemos.identity._invoke_claude_print",
        lambda prompt, model: "# Identity\n\nMocked output",
    )

    out = bootstrap(tmp_path)
    assert out.exists()


def test_bootstrap_force_bypasses_gate(tmp_path: Path, monkeypatch):
    sessions = tmp_path / "Sessions"
    sessions.mkdir()
    (sessions / "2026-01-01-x.md").write_text(
        "---\ndate: 2026-01-01\n---\nbody\n", encoding="utf-8"
    )
    (tmp_path / "mnemos.yaml").write_text(
        "schema_version: 2\nidentity:\n  bootstrap_threshold_pct: 50\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "mnemos.identity._count_eligible_jsonls_for_bootstrap",
        lambda vault: 10,
    )
    monkeypatch.setattr(
        "mnemos.identity._invoke_claude_print",
        lambda prompt, model: "# Identity\n\nForced output",
    )
    out = bootstrap(tmp_path, force=True)
    assert out.exists()
