"""Tests for scripts/backfill_cwd_frontmatter.py — cwd frontmatter backfill."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make scripts/ importable
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from backfill_cwd_frontmatter import (  # noqa: E402
    extract_cwd_from_jsonl,
    parse_ledger,
    upsert_cwd_frontmatter,
    run_backfill,
)


def _write_jsonl(path: Path, messages: list[dict]) -> None:
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for msg in messages:
            fh.write(json.dumps(msg) + "\n")


def test_extract_cwd_from_jsonl_finds_first_occurrence(tmp_path: Path) -> None:
    jsonl = tmp_path / "a.jsonl"
    _write_jsonl(jsonl, [
        {"type": "metadata", "sessionId": "x"},
        {"type": "user", "cwd": "C:\\Projects\\farcry", "content": "hi"},
        {"type": "assistant", "cwd": "C:\\Projects\\farcry"},
    ])
    assert extract_cwd_from_jsonl(jsonl) == "C:\\Projects\\farcry"


def test_extract_cwd_from_jsonl_missing_returns_none(tmp_path: Path) -> None:
    jsonl = tmp_path / "a.jsonl"
    _write_jsonl(jsonl, [{"type": "metadata", "sessionId": "x"}])
    assert extract_cwd_from_jsonl(jsonl) is None


def test_extract_cwd_from_jsonl_missing_file_returns_none(tmp_path: Path) -> None:
    assert extract_cwd_from_jsonl(tmp_path / "nope.jsonl") is None


def test_parse_ledger_returns_ok_rows(tmp_path: Path) -> None:
    ledger = tmp_path / "processed.tsv"
    ledger.write_text(
        "ts1\tOK\tC:\\proj\\a.jsonl\t2026-04-01-foo.md\n"
        "ts2\tSKIP\tC:\\proj\\b.jsonl\tnone\n"
        "ts3\tOK\tC:\\proj\\c.jsonl\t2026-04-02-bar.md\n",
        encoding="utf-8",
    )
    rows = parse_ledger(ledger)
    assert len(rows) == 2
    assert rows[0].jsonl == "C:\\proj\\a.jsonl"
    assert rows[0].session_md == "2026-04-01-foo.md"
    assert rows[1].session_md == "2026-04-02-bar.md"


def test_upsert_cwd_frontmatter_adds_field(tmp_path: Path) -> None:
    md = tmp_path / "session.md"
    md.write_text(
        "---\n"
        "date: 2026-04-01\n"
        "project: GYP\n"
        "tags: [session-log]\n"
        "---\n"
        "\n# body\n",
        encoding="utf-8",
    )
    changed = upsert_cwd_frontmatter(md, "C:\\Projects\\gyp")
    assert changed is True
    text = md.read_text(encoding="utf-8")
    assert "cwd: C:\\Projects\\gyp" in text
    assert "project: GYP" in text  # existing fields preserved


def test_upsert_cwd_frontmatter_idempotent(tmp_path: Path) -> None:
    md = tmp_path / "session.md"
    md.write_text(
        "---\n"
        "date: 2026-04-01\n"
        "cwd: C:\\Projects\\gyp\n"
        "project: GYP\n"
        "---\n"
        "\nbody\n",
        encoding="utf-8",
    )
    changed = upsert_cwd_frontmatter(md, "C:\\Projects\\gyp")
    assert changed is False


def test_upsert_cwd_frontmatter_corrupt_frontmatter_returns_false(tmp_path: Path) -> None:
    md = tmp_path / "session.md"
    md.write_text("no frontmatter here\n", encoding="utf-8")
    changed = upsert_cwd_frontmatter(md, "C:\\x")
    assert changed is False


def test_run_backfill_end_to_end(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    sessions = vault / "Sessions"
    sessions.mkdir(parents=True)

    (sessions / "2026-04-01-foo.md").write_text(
        "---\ndate: 2026-04-01\nproject: GYP\n---\nbody\n",
        encoding="utf-8",
    )
    (sessions / "2026-04-02-bar.md").write_text(
        "---\ndate: 2026-04-02\ncwd: C:\\existing\nproject: GYP\n---\nbody\n",
        encoding="utf-8",
    )

    ledger = tmp_path / "processed.tsv"
    jsonl_a = tmp_path / "a.jsonl"
    jsonl_b = tmp_path / "b.jsonl"
    _write_jsonl(jsonl_a, [{"cwd": "C:\\Projects\\gyp"}])
    _write_jsonl(jsonl_b, [{"cwd": "C:\\Projects\\gyp"}])
    ledger.write_text(
        f"ts1\tOK\t{jsonl_a}\t2026-04-01-foo.md\n"
        f"ts2\tOK\t{jsonl_b}\t2026-04-02-bar.md\n",
        encoding="utf-8",
    )

    report = run_backfill(vault=vault, ledger=ledger, apply=True)
    assert report.updated == 1
    assert report.skipped_already_present == 1
    assert report.jsonl_missing == 0
    assert report.errors == 0

    # Re-run is idempotent
    report2 = run_backfill(vault=vault, ledger=ledger, apply=True)
    assert report2.updated == 0
    assert report2.skipped_already_present == 2


def test_run_backfill_jsonl_missing(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    sessions = vault / "Sessions"
    sessions.mkdir(parents=True)
    (sessions / "2026-04-01-foo.md").write_text(
        "---\ndate: 2026-04-01\nproject: GYP\n---\nbody\n",
        encoding="utf-8",
    )

    ledger = tmp_path / "processed.tsv"
    ledger.write_text(
        "ts1\tOK\tC:\\does-not-exist.jsonl\t2026-04-01-foo.md\n",
        encoding="utf-8",
    )

    report = run_backfill(vault=vault, ledger=ledger, apply=True)
    assert report.updated == 0
    assert report.jsonl_missing == 1


def test_run_backfill_dry_run_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    sessions = vault / "Sessions"
    sessions.mkdir(parents=True)
    md = sessions / "2026-04-01-foo.md"
    md.write_text(
        "---\ndate: 2026-04-01\nproject: GYP\n---\nbody\n",
        encoding="utf-8",
    )
    orig = md.read_text(encoding="utf-8")

    ledger = tmp_path / "processed.tsv"
    jsonl = tmp_path / "a.jsonl"
    _write_jsonl(jsonl, [{"cwd": "C:\\Projects\\gyp"}])
    ledger.write_text(
        f"ts1\tOK\t{jsonl}\t2026-04-01-foo.md\n",
        encoding="utf-8",
    )

    report = run_backfill(vault=vault, ledger=ledger, apply=False)
    assert report.updated == 1  # dry-run still counts what WOULD happen
    assert md.read_text(encoding="utf-8") == orig  # unchanged
