"""Tests for mnemos.pending — `.mnemos-pending.json` read/write/upsert."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mnemos.pending import (
    PENDING_FILENAME,
    SCHEMA_VERSION,
    PendingSource,
    PendingState,
    load,
    pending_path,
    save,
    upsert_source,
)


class TestLoadEmpty:
    def test_missing_file_returns_empty_state(self, tmp_vault: Path) -> None:
        state = load(tmp_vault)
        assert state.version == SCHEMA_VERSION
        assert state.sources == []


class TestSaveAndLoadRoundtrip:
    def test_roundtrip_preserves_fields(self, tmp_vault: Path) -> None:
        src = PendingSource(
            id="claude-code-jsonl",
            path="~/.claude/projects",
            kind="raw-jsonl",
            status="in-progress",
            total=244,
            processed=5,
            last_action="pilot-accepted",
        )
        save(tmp_vault, PendingState(sources=[src]))

        reloaded = load(tmp_vault)
        assert len(reloaded.sources) == 1
        got = reloaded.sources[0]
        assert got.id == "claude-code-jsonl"
        assert got.path == "~/.claude/projects"
        assert got.kind == "raw-jsonl"
        assert got.status == "in-progress"
        assert got.total == 244
        assert got.processed == 5
        assert got.last_action == "pilot-accepted"
        assert got.discovered_at  # auto-populated

    def test_save_writes_to_vault_root(self, tmp_vault: Path) -> None:
        save(tmp_vault, PendingState())
        assert (tmp_vault / PENDING_FILENAME).exists()
        assert pending_path(tmp_vault) == tmp_vault / PENDING_FILENAME

    def test_save_emits_valid_json_with_version(self, tmp_vault: Path) -> None:
        save(tmp_vault, PendingState(sources=[
            PendingSource(id="a", path="/x", kind="raw-jsonl"),
        ]))
        raw = json.loads((tmp_vault / PENDING_FILENAME).read_text(encoding="utf-8"))
        assert raw["version"] == SCHEMA_VERSION
        assert raw["sources"][0]["id"] == "a"


class TestUpsertSource:
    def test_appends_new_source(self, tmp_vault: Path) -> None:
        state = upsert_source(
            tmp_vault,
            PendingSource(id="cc", path="/p", kind="raw-jsonl"),
        )
        assert len(state.sources) == 1
        assert state.sources[0].id == "cc"

    def test_replaces_existing_source_by_id(self, tmp_vault: Path) -> None:
        upsert_source(
            tmp_vault,
            PendingSource(id="cc", path="/p", kind="raw-jsonl", processed=5),
        )
        upsert_source(
            tmp_vault,
            PendingSource(
                id="cc",
                path="/p",
                kind="raw-jsonl",
                status="done",
                processed=244,
                total=244,
            ),
        )

        state = load(tmp_vault)
        assert len(state.sources) == 1
        assert state.sources[0].status == "done"
        assert state.sources[0].processed == 244

    def test_keeps_other_sources_untouched(self, tmp_vault: Path) -> None:
        upsert_source(
            tmp_vault,
            PendingSource(id="cc", path="/p", kind="raw-jsonl"),
        )
        upsert_source(
            tmp_vault,
            PendingSource(id="chatgpt", path="/q", kind="chatgpt-export"),
        )

        state = load(tmp_vault)
        ids = [s.id for s in state.sources]
        assert ids == ["cc", "chatgpt"]


class TestValidation:
    def test_invalid_status_rejected(self) -> None:
        with pytest.raises(ValueError, match="invalid status"):
            PendingSource(id="x", path="/p", kind="raw-jsonl", status="bogus")  # type: ignore[arg-type]

    def test_unknown_schema_version_rejected(self, tmp_vault: Path) -> None:
        (tmp_vault / PENDING_FILENAME).write_text(
            json.dumps({"version": 999, "sources": []}),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="unsupported pending schema version"):
            load(tmp_vault)


class TestStateGet:
    def test_get_returns_matching_source(self) -> None:
        state = PendingState(sources=[
            PendingSource(id="a", path="/x", kind="raw-jsonl"),
            PendingSource(id="b", path="/y", kind="chatgpt-export"),
        ])
        assert state.get("b").path == "/y"
        assert state.get("missing") is None
