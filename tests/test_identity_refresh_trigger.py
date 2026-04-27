"""Tests for identity.refresh() reading session-delta gate from config."""
from pathlib import Path

from mnemos.identity import refresh


def test_refresh_uses_config_session_delta(tmp_path: Path, monkeypatch):
    """refresh() should respect cfg.identity.refresh_session_delta, not hardcoded 10."""
    # Setup: existing identity, 5 new sessions since last refresh
    identity_dir = tmp_path / "_identity"
    identity_dir.mkdir()
    (identity_dir / "L0-identity.md").write_text(
        "---\nsession_count_at_refresh: 0\n---\nbody\n", encoding="utf-8"
    )
    sessions = tmp_path / "Sessions"
    sessions.mkdir()
    for i in range(5):
        (sessions / f"2026-01-{i+1:02d}-x.md").write_text(
            f"---\ndate: 2026-01-{i+1:02d}\n---\n", encoding="utf-8"
        )
    # Config: delta = 3 -> trigger should fire (5 >= 3)
    (tmp_path / "mnemos.yaml").write_text(
        "schema_version: 2\nidentity:\n  refresh_session_delta: 3\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "mnemos.identity._invoke_claude_print",
        lambda prompt, model: "# Updated\n",
    )
    monkeypatch.setattr(
        "mnemos.identity._has_identity_relevant_new_tags",
        lambda *a, **kw: True,  # bypass tag relevance for unit test
    )
    out = refresh(tmp_path)
    assert out is not None  # fired


def test_refresh_skips_below_session_delta(tmp_path: Path):
    identity_dir = tmp_path / "_identity"
    identity_dir.mkdir()
    (identity_dir / "L0-identity.md").write_text(
        "---\nsession_count_at_refresh: 0\n---\nbody\n", encoding="utf-8"
    )
    sessions = tmp_path / "Sessions"
    sessions.mkdir()
    for i in range(2):
        (sessions / f"2026-01-{i+1:02d}-x.md").write_text(
            f"---\ndate: 2026-01-{i+1:02d}\n---\n", encoding="utf-8"
        )
    (tmp_path / "mnemos.yaml").write_text(
        "schema_version: 2\nidentity:\n  refresh_session_delta: 5\n",
        encoding="utf-8",
    )
    out = refresh(tmp_path)
    assert out is None  # skipped (2 < 5)
