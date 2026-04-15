import os
from pathlib import Path

import pytest


def test_resolve_ledger_path_default(monkeypatch):
    from mnemos.auto_refine import resolve_ledger_path

    monkeypatch.delenv("MNEMOS_REFINE_LEDGER", raising=False)
    path = resolve_ledger_path()
    assert path.name == "processed.tsv"
    assert "mnemos-refine-transcripts" in str(path)
    assert "state" in str(path)


def test_resolve_ledger_path_env_override(monkeypatch, tmp_path):
    from mnemos.auto_refine import resolve_ledger_path

    custom = tmp_path / "custom_ledger.tsv"
    monkeypatch.setenv("MNEMOS_REFINE_LEDGER", str(custom))
    assert resolve_ledger_path() == custom


def _write_jsonl(projects_dir: Path, name: str, mtime: float) -> Path:
    path = projects_dir / "proj" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}\n", encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


def test_pick_recent_picks_last_n_by_mtime(tmp_path):
    from mnemos.auto_refine import pick_recent_jsonls

    projects = tmp_path / "projects"
    old = _write_jsonl(projects, "old.jsonl", 1_000_000)
    mid = _write_jsonl(projects, "mid.jsonl", 2_000_000)
    new = _write_jsonl(projects, "new.jsonl", 3_000_000)

    ledger = tmp_path / "ledger.tsv"
    picked = pick_recent_jsonls(projects, ledger, n=2)
    assert picked == [new, mid]


def test_pick_recent_skips_ledger_entries(tmp_path):
    from mnemos.auto_refine import pick_recent_jsonls

    projects = tmp_path / "projects"
    a = _write_jsonl(projects, "a.jsonl", 1_000_000)
    b = _write_jsonl(projects, "b.jsonl", 2_000_000)
    c = _write_jsonl(projects, "c.jsonl", 3_000_000)

    ledger = tmp_path / "ledger.tsv"
    ledger.write_text(
        f"OK\t{c}\tnote.md\n",
        encoding="utf-8",
    )
    picked = pick_recent_jsonls(projects, ledger, n=3)
    assert picked == [b, a]


def test_pick_recent_handles_missing_projects_dir(tmp_path):
    from mnemos.auto_refine import pick_recent_jsonls

    missing = tmp_path / "nope"
    assert pick_recent_jsonls(missing, tmp_path / "ledger.tsv", n=3) == []


def test_pick_recent_handles_missing_ledger(tmp_path):
    from mnemos.auto_refine import pick_recent_jsonls

    projects = tmp_path / "projects"
    a = _write_jsonl(projects, "a.jsonl", 1_000_000)
    picked = pick_recent_jsonls(projects, tmp_path / "never.tsv", n=3)
    assert picked == [a]
