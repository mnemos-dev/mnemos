"""Tests for mnemos.onboarding — discover/classify/format helpers."""
from __future__ import annotations

from pathlib import Path

import pytest

from mnemos.onboarding import (
    SECS_PER_CURATED_FILE,
    SECS_PER_RAW_FILE,
    DiscoveredSource,
    classify,
    discover,
    format_estimate,
)


class TestClassify:
    def test_jsonl_is_raw(self) -> None:
        assert classify("raw-jsonl") == "raw"

    def test_md_is_curated(self) -> None:
        assert classify("curated-md") == "curated"

    def test_unknown_kind_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown source kind"):
            classify("nonsense")  # type: ignore[arg-type]


class TestFormatEstimate:
    def test_seconds(self) -> None:
        assert format_estimate(45) == "~45 sn"

    def test_minutes(self) -> None:
        assert format_estimate(120) == "~2 dk"
        assert format_estimate(2400) == "~40 dk"

    def test_hours(self) -> None:
        assert format_estimate(7200) == "~2.0 sa"


class TestDiscoveryEmpty:
    def test_empty_vault_no_claude_dir_returns_empty(self, tmp_vault: Path, tmp_path: Path) -> None:
        # Point claude_projects_dir at an empty directory so no JSONL is found.
        empty = tmp_path / "empty-claude"
        empty.mkdir()
        # tmp_vault has Sessions/ + Topics/ but they are empty.
        assert discover(tmp_vault, claude_projects_dir=empty) == []

    def test_nonexistent_claude_dir_treated_as_missing(self, tmp_vault: Path, tmp_path: Path) -> None:
        ghost = tmp_path / "does-not-exist"
        assert discover(tmp_vault, claude_projects_dir=ghost) == []


class TestDiscoveryClaudeCode:
    def test_finds_jsonl_recursively(self, tmp_vault: Path, tmp_path: Path) -> None:
        cc_dir = tmp_path / "claude-projects"
        proj_a = cc_dir / "C--Projeler-mnemos"
        proj_b = cc_dir / "C--Projeler-other"
        proj_a.mkdir(parents=True)
        proj_b.mkdir(parents=True)
        (proj_a / "session1.jsonl").write_text("{}\n", encoding="utf-8")
        (proj_a / "session2.jsonl").write_text("{}\n", encoding="utf-8")
        (proj_b / "session3.jsonl").write_text("{}\n", encoding="utf-8")
        # Non-jsonl should be ignored
        (proj_a / "notes.txt").write_text("hi", encoding="utf-8")

        sources = discover(tmp_vault, claude_projects_dir=cc_dir)

        assert len(sources) == 1
        cc = sources[0]
        assert cc.id == "claude-code-jsonl"
        assert cc.kind == "raw-jsonl"
        assert cc.classification == "raw"
        assert cc.file_count == 3
        assert cc.estimated_seconds == 3 * SECS_PER_RAW_FILE
        assert len(cc.sample_files) == 3


class TestDiscoveryVaultCurated:
    def test_finds_sessions_memory_topics(self, tmp_vault: Path, tmp_path: Path) -> None:
        # tmp_vault already has Sessions/ + Topics/
        (tmp_vault / "memory").mkdir()
        (tmp_vault / "Sessions" / "a.md").write_text("# a", encoding="utf-8")
        (tmp_vault / "Sessions" / "b.md").write_text("# b", encoding="utf-8")
        (tmp_vault / "memory" / "x.md").write_text("# x", encoding="utf-8")
        (tmp_vault / "Topics" / "ProcureTrack.md").write_text("# pt", encoding="utf-8")

        empty_cc = tmp_path / "empty"
        empty_cc.mkdir()
        sources = discover(tmp_vault, claude_projects_dir=empty_cc)

        ids = [s.id for s in sources]
        assert ids == ["vault-sessions", "vault-memory", "vault-topics"]

        sessions = sources[0]
        assert sessions.kind == "curated-md"
        assert sessions.classification == "curated"
        assert sessions.file_count == 2
        assert sessions.estimated_seconds == 2 * SECS_PER_CURATED_FILE

    def test_ignores_non_md_files(self, tmp_vault: Path, tmp_path: Path) -> None:
        (tmp_vault / "Sessions" / "note.md").write_text("# x", encoding="utf-8")
        (tmp_vault / "Sessions" / "scratch.txt").write_text("nope", encoding="utf-8")
        (tmp_vault / "Sessions" / "image.png").write_bytes(b"\x89PNG")

        empty_cc = tmp_path / "empty"
        empty_cc.mkdir()
        sources = discover(tmp_vault, claude_projects_dir=empty_cc)

        assert sources[0].file_count == 1

    def test_missing_subdir_omitted(self, tmp_path: Path) -> None:
        # Bare vault — no Sessions/, no Topics/, no memory/
        bare = tmp_path / "bare-vault"
        bare.mkdir()
        empty_cc = tmp_path / "empty"
        empty_cc.mkdir()
        assert discover(bare, claude_projects_dir=empty_cc) == []


class TestApplyDecisionNonMining:
    """test_apply_decision_non_mining — skip + raw 'register-only' branches.

    The 'process now' branch invokes MnemosApp (heavy: chromadb, watcher) so
    it lives in the integration suite. Here we cover the lightweight branches
    that only touch `.mnemos-pending.json`.
    """

    def test_skip_writes_skipped_status(self, config, tmp_vault: Path) -> None:
        from mnemos import pending
        from mnemos.cli import _apply_decision

        src = DiscoveredSource(
            id="vault-sessions", kind="curated-md",
            root_path=str(tmp_vault / "Sessions"), file_count=4,
        )
        _apply_decision(config, src, "skip")

        state = pending.load(tmp_vault)
        assert state.get("vault-sessions").status == "skipped-by-user"
        assert state.get("vault-sessions").last_action == "skipped-during-init"

    def test_raw_source_registered_pending_with_refine_hint(
        self, config, tmp_vault: Path, capsys: pytest.CaptureFixture
    ) -> None:
        from mnemos import pending
        from mnemos.cli import _apply_decision

        src = DiscoveredSource(
            id="claude-code-jsonl", kind="raw-jsonl",
            root_path="/fake/claude/projects", file_count=244,
        )
        _apply_decision(config, src, "process")  # raw forced to register-only

        state = pending.load(tmp_vault)
        entry = state.get("claude-code-jsonl")
        assert entry.status == "pending"
        assert entry.last_action == "awaiting-refine-skill"
        assert entry.total == 244

        captured = capsys.readouterr()
        assert "/mnemos-refine-transcripts" in captured.out

    def test_later_decision_for_curated_records_deferred(
        self, config, tmp_vault: Path
    ) -> None:
        from mnemos import pending
        from mnemos.cli import _apply_decision

        src = DiscoveredSource(
            id="vault-topics", kind="curated-md",
            root_path=str(tmp_vault / "Topics"), file_count=12,
        )
        _apply_decision(config, src, "later")

        entry = pending.load(tmp_vault).get("vault-topics")
        assert entry.status == "pending"
        assert entry.last_action == "deferred-by-user"


class TestPendingHelpers:
    """test_pending_helpers — onboarding's thin wrappers around mnemos.pending."""

    def test_mark_in_progress(self, tmp_vault: Path) -> None:
        from mnemos import onboarding, pending

        onboarding.mark_in_progress(
            tmp_vault, source_id="x", kind="curated-md",
            root_path="/p", file_count=7,
        )
        entry = pending.load(tmp_vault).get("x")
        assert entry.status == "in-progress"
        assert entry.last_action == "mining"
        assert entry.total == 7

    def test_mark_done_records_processed(self, tmp_vault: Path) -> None:
        from mnemos import onboarding, pending

        onboarding.mark_done(
            tmp_vault, source_id="x", kind="curated-md",
            root_path="/p", file_count=10, processed=8,
            last_action="mined-via-import",
        )
        entry = pending.load(tmp_vault).get("x")
        assert entry.status == "done"
        assert entry.processed == 8
        assert entry.last_action == "mined-via-import"

    def test_register_pending_uses_caller_action(self, tmp_vault: Path) -> None:
        from mnemos import onboarding, pending

        onboarding.register_pending(
            tmp_vault, source_id="cc", kind="raw-jsonl",
            root_path="/r", file_count=200,
            last_action="awaiting-refine-skill",
        )
        entry = pending.load(tmp_vault).get("cc")
        assert entry.status == "pending"
        assert entry.last_action == "awaiting-refine-skill"


# TestImportClaudeCode (was: register-only `mnemos import claude-code` path)
# was REMOVED in v1.0. The /mnemos-refine-transcripts skill now scans
# ~/.claude/projects directly, so the separate registration step + the
# `_import_claude_code` helper are gone. See mnemos/cli.py `cmd_import`
# for the friendly removal message that fires when users invoke the
# legacy subcommand.


# TestImportPathValidation (was: file vs directory rejection for the
# `_import_chatgpt` / `_import_markdown` helpers) was REMOVED in v1.0
# alongside the entire `mnemos import` command family. See test_cli.py
# for the removal-message regressions that lock the friendly shim down.


class TestDiscoveryOrdering:
    def test_claude_first_then_vault(self, tmp_vault: Path, tmp_path: Path) -> None:
        cc_dir = tmp_path / "claude-projects"
        cc_dir.mkdir()
        (cc_dir / "s.jsonl").write_text("{}", encoding="utf-8")
        (tmp_vault / "Sessions" / "a.md").write_text("#", encoding="utf-8")

        sources = discover(tmp_vault, claude_projects_dir=cc_dir)
        assert [s.id for s in sources] == ["claude-code-jsonl", "vault-sessions"]
