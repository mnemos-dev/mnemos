"""Identity Layer tests."""
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from mnemos.identity import bootstrap, refresh, rollback, show, IdentityError, _has_identity_relevant_new_tags

PROMPT_PATH = Path(__file__).parent.parent / "docs" / "prompts" / "identity-bootstrap.md"


def test_identity_bootstrap_prompt_exists():
    assert PROMPT_PATH.exists(), f"Missing canonical prompt: {PROMPT_PATH}"


def test_identity_bootstrap_prompt_documents_sections():
    content = PROMPT_PATH.read_text(encoding="utf-8")
    for section in [
        "Çalışma stili",
        "Teknik tercihler",
        "Reddedilen yaklaşımlar",
        "Aktif projeler",
        "Yörüngedeki insanlar",
        "Ustalaşmış araçlar",
        "Revize edilen kararlar",
    ]:
        assert section in content, f"Missing section: {section}"


def test_identity_bootstrap_prompt_documents_scope_notation():
    content = PROMPT_PATH.read_text(encoding="utf-8")
    assert "(general)" in content
    assert "(proj/" in content


def test_identity_bootstrap_prompt_documents_size_limits():
    content = PROMPT_PATH.read_text(encoding="utf-8")
    assert "max" in content.lower() and "madde" in content.lower()


def test_identity_bootstrap_prompt_documents_context_cap():
    content = PROMPT_PATH.read_text(encoding="utf-8")
    assert "150K" in content or "150000" in content


def _make_test_vault(n_sessions: int = 3) -> Path:
    """Create a temp vault with N fake Session/.md files."""
    vault = Path(tempfile.mkdtemp(prefix="mnemos-test-"))
    sessions = vault / "Sessions"
    sessions.mkdir()
    for i in range(n_sessions):
        (sessions / f"2026-01-{i+1:02d}-test-session-{i}.md").write_text(
            f"---\ndate: 2026-01-{i+1:02d}\nproject: TestProj\n---\n\n# Test Session {i}\n\nLorem ipsum.\n",
            encoding="utf-8",
        )
    return vault


def test_bootstrap_creates_identity_file():
    vault = _make_test_vault(3)
    with patch("mnemos.identity._invoke_claude_print") as mock_invoke:
        mock_invoke.return_value = (
            "---\ngenerated_from: 3 sessions\nlast_refreshed: 2026-04-25\n"
            "session_count_at_refresh: 3\nschema_version: 1\n---\n\n"
            "# User Identity\n\n## Çalışma stili\n- (general) Test stili\n"
        )
        # force=True bypasses the v1.1 readiness gate; this test exercises the
        # output-writing path, not the gate.
        result = bootstrap(vault, force=True)
    identity_path = vault / "_identity" / "L0-identity.md"
    assert identity_path.exists()
    assert "User Identity" in identity_path.read_text(encoding="utf-8")


def test_bootstrap_creates_history_snapshot():
    vault = _make_test_vault(3)
    with patch("mnemos.identity._invoke_claude_print") as mock_invoke:
        mock_invoke.return_value = "---\ngenerated_from: 3 sessions\n---\n\n# User Identity\n"
        bootstrap(vault, force=True)
    history_dir = vault / "_identity" / "_history"
    snapshots = list(history_dir.glob("*-bootstrap.md"))
    assert len(snapshots) == 1


def test_bootstrap_raises_when_no_sessions():
    vault = _make_test_vault(0)
    with pytest.raises(IdentityError, match="no sessions"):
        bootstrap(vault)


def test_bootstrap_applies_context_cap_on_large_vault():
    """When total input > 150K tokens, hybrid sampling is applied."""
    vault = _make_test_vault(0)
    sessions = vault / "Sessions"
    # Create 120 sessions of ~2K each = ~240K total → cap kicks in
    for i in range(120):
        (sessions / f"2026-{i//30+1:02d}-{(i%30)+1:02d}-test-{i}.md").write_text(
            "---\ndate: 2026-01-01\nproject: T\n---\n\n# T\n\n" + ("x " * 1000),
            encoding="utf-8",
        )
    with patch("mnemos.identity._invoke_claude_print") as mock_invoke:
        mock_invoke.return_value = "---\n---\n\n# User Identity"
        bootstrap(vault)
        # Inspect the input passed to claude --print: should be capped
        passed_input = mock_invoke.call_args[0][0]  # first positional arg
        # Hybrid: should reference fewer than 120 sessions
        assert passed_input.count("# 2026-") < 120


def test_refresh_skips_when_no_new_sessions():
    vault = _make_test_vault(0)
    identity_dir = vault / "_identity"
    identity_dir.mkdir()
    (identity_dir / "L0-identity.md").write_text(
        "---\nlast_refreshed: 2026-04-25\nsession_count_at_refresh: 3\n---\n\n# User Identity\n",
        encoding="utf-8",
    )
    result = refresh(vault, force=False)
    assert result is None  # skipped


def test_refresh_with_new_sessions_invokes_llm():
    vault = _make_test_vault(0)
    identity_dir = vault / "_identity"
    identity_dir.mkdir()
    (identity_dir / "L0-identity.md").write_text(
        "---\nlast_refreshed: 2026-04-25\nsession_count_at_refresh: 0\n---\n\n# User Identity\n",
        encoding="utf-8",
    )
    sessions = vault / "Sessions"
    for i in range(11):  # >10 trigger threshold
        (sessions / f"2026-05-{i+1:02d}-new-session-{i}.md").write_text(
            f"---\ndate: 2026-05-{i+1:02d}\ntags: [session-log, proj/newproj]\n---\n\n# New {i}",
            encoding="utf-8",
        )
    with patch("mnemos.identity._invoke_claude_print") as mock_invoke:
        mock_invoke.return_value = "---\nsession_count_at_refresh: 11\n---\n\n# User Identity (refreshed)"
        result = refresh(vault, force=True)  # force bypasses trigger
    assert result is not None
    assert "refreshed" in result.read_text(encoding="utf-8")


def test_refresh_creates_pre_refresh_backup():
    vault = _make_test_vault(0)
    identity_dir = vault / "_identity"
    identity_dir.mkdir()
    identity_path = identity_dir / "L0-identity.md"
    identity_path.write_text(
        "---\nlast_refreshed: 2026-04-25\nsession_count_at_refresh: 0\n---\n\n# Original",
        encoding="utf-8",
    )
    sessions = vault / "Sessions"
    for i in range(11):
        (sessions / f"2026-05-{i+1:02d}-x.md").write_text(
            f"---\ndate: 2026-05-{i+1:02d}\ntags: [session-log, proj/x]\n---\n", encoding="utf-8"
        )
    with patch("mnemos.identity._invoke_claude_print") as mock:
        mock.return_value = "---\n---\n\n# Updated"
        refresh(vault, force=True)
    # Either git commit happened (check log) or .bak file created
    bak_files = list(identity_dir.glob("L0-identity.md.bak-*"))
    assert len(bak_files) == 1, f"expected exactly 1 .bak file, found {bak_files}"


def test_has_identity_relevant_new_tags_true_for_new_proj():
    """If a new session has proj/<new-name> not in profile, returns True."""
    profile_text = "## Aktif projeler\n- [[Mnemos]]\n- [[ProcureTrack]]\n"
    new_session_paths = [Path("/tmp/x.md")]
    with patch("pathlib.Path.read_text", return_value="---\ntags: [session-log, proj/newcustomer]\n---\n"):
        assert _has_identity_relevant_new_tags(profile_text, new_session_paths) is True


def test_has_identity_relevant_new_tags_false_for_existing_only():
    profile_text = "## Aktif projeler\n- [[Mnemos]]\n- [[ProcureTrack]]\n"
    new_session_paths = [Path("/tmp/x.md")]
    with patch("pathlib.Path.read_text", return_value="---\ntags: [session-log, proj/mnemos]\n---\n"):
        assert _has_identity_relevant_new_tags(profile_text, new_session_paths) is False


def test_rollback_to_latest_bak():
    vault = _make_test_vault(0)
    identity_dir = vault / "_identity"
    identity_dir.mkdir()
    identity_path = identity_dir / "L0-identity.md"
    identity_path.write_text("# Current", encoding="utf-8")
    bak = identity_dir / "L0-identity.md.bak-2026-04-24-1200"
    bak.write_text("# Old version", encoding="utf-8")

    result = rollback(vault, target=None, confirm=True)
    assert result == identity_path
    assert "Old version" in identity_path.read_text(encoding="utf-8")


def test_rollback_specific_date():
    vault = _make_test_vault(0)
    identity_dir = vault / "_identity"
    identity_dir.mkdir()
    identity_path = identity_dir / "L0-identity.md"
    identity_path.write_text("# Current", encoding="utf-8")
    (identity_dir / "L0-identity.md.bak-2026-04-24-1200").write_text("# A", encoding="utf-8")
    (identity_dir / "L0-identity.md.bak-2026-04-25-0900").write_text("# B", encoding="utf-8")

    rollback(vault, target="2026-04-24-1200", confirm=True)
    assert identity_path.read_text(encoding="utf-8") == "# A"


def test_rollback_raises_when_no_baks():
    vault = _make_test_vault(0)
    (vault / "_identity").mkdir()
    (vault / "_identity" / "L0-identity.md").write_text("# X", encoding="utf-8")

    with pytest.raises(IdentityError, match="no backup"):
        rollback(vault, target=None, confirm=True)


def test_show_returns_identity_content():
    vault = _make_test_vault(0)
    (vault / "_identity").mkdir()
    (vault / "_identity" / "L0-identity.md").write_text(
        "---\nlast_refreshed: 2026-04-25\n---\n\n# User Identity\n",
        encoding="utf-8",
    )
    output = show(vault)
    assert "User Identity" in output


# ---------------------------------------------------------------------------
# handle_status — Identity Layer metadata (Task 14)
# ---------------------------------------------------------------------------


def test_handle_status_includes_identity_last_refreshed(tmp_path):
    """mnemos_status MCP tool returns identity refresh metadata."""
    from mnemos.config import MnemosConfig
    from mnemos.server import MnemosApp

    vault = tmp_path / "vault"
    (vault / "Sessions").mkdir(parents=True)
    (vault / "_identity").mkdir()
    (vault / "_identity" / "L0-identity.md").write_text(
        "---\nlast_refreshed: 2026-04-25\nsession_count_at_refresh: 5\n---\n\n# User Identity\n",
        encoding="utf-8",
    )

    cfg = MnemosConfig(vault_path=str(vault), languages=["en"])
    app = MnemosApp(cfg, chromadb_in_memory=True)
    status = app.handle_status()
    assert "identity_last_refreshed" in status
    assert status["identity_last_refreshed"] == "2026-04-25"
    assert status["identity_session_count_at_refresh"] == 5


def test_handle_status_identity_none_when_not_bootstrapped(tmp_path):
    """No L0-identity.md → identity_last_refreshed is None."""
    from mnemos.config import MnemosConfig
    from mnemos.server import MnemosApp

    vault = tmp_path / "vault"
    (vault / "Sessions").mkdir(parents=True)

    cfg = MnemosConfig(vault_path=str(vault), languages=["en"])
    app = MnemosApp(cfg, chromadb_in_memory=True)
    status = app.handle_status()
    assert status.get("identity_last_refreshed") is None
    assert status.get("identity_session_count_at_refresh") is None
