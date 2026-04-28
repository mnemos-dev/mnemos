"""v1.2.1 — `mnemos refine-ledger --normalize` CLI smoke."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


def test_cli_normalize_repairs_corrupted_ledger(tmp_path, capsys, monkeypatch):
    from mnemos.cli import main

    ledger = tmp_path / "processed.tsv"
    ledger.write_text(
        "C:/x/a.jsonl\tOK\t2026-04-28-aaa.md\n"
        "C:/x/a.jsonl\tOK\t2026-04-28-aaa.md\n"  # duplicate
        "junk-no-tabs-here-at-all\n"             # malformed
        "C:/x/b.jsonl\tOK\t2026-04-28-bbb.md\n",
        encoding="utf-8",
    )

    rc = main(["refine-ledger", "--normalize", "--ledger", str(ledger)])
    assert rc == 0

    out = ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(out) == 2  # 1 dup + 1 malformed dropped, 2 unique paths kept

    captured = capsys.readouterr()
    assert "Ledger normalized" in captured.out
    assert "Malformed dropped:  1" in captured.out
    assert "Duplicates dropped: 1" in captured.out


def test_cli_dry_run_does_not_modify(tmp_path, capsys):
    from mnemos.cli import main

    ledger = tmp_path / "processed.tsv"
    original = (
        "C:/x/a.jsonl\tOK\taaa.md\n"
        "junk-no-tabs\n"
        "C:/x/a.jsonl\tOK\taaa.md\n"
    )
    ledger.write_text(original, encoding="utf-8")

    rc = main(["refine-ledger", "--normalize", "--ledger", str(ledger), "--dry-run"])
    assert rc == 0

    # File untouched
    assert ledger.read_text(encoding="utf-8") == original

    captured = capsys.readouterr()
    assert "Dry run" in captured.out
    assert "Malformed (would be dropped): 1" in captured.out


def test_cli_missing_ledger_reports_error(tmp_path, capsys):
    from mnemos.cli import main

    rc = main(["refine-ledger", "--normalize", "--ledger", str(tmp_path / "nope.tsv")])
    assert rc == 1

    captured = capsys.readouterr()
    assert "Ledger not found" in captured.err
