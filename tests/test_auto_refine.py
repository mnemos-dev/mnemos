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
        f"{c}\tOK\tnote.md\n",
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


def test_pick_recent_parses_real_ledger_format(tmp_path):
    from mnemos.auto_refine import pick_recent_jsonls

    projects = tmp_path / "projects"
    a = _write_jsonl(projects, "a.jsonl", 1_000_000)
    b = _write_jsonl(projects, "b.jsonl", 2_000_000)
    c = _write_jsonl(projects, "c.jsonl", 3_000_000)

    ledger = tmp_path / "ledger.tsv"
    ledger.write_text(
        f"{a}\tOK\tnote1.md\n{c}\tSKIP\tbos-transcript\n",
        encoding="utf-8",
    )
    picked = pick_recent_jsonls(projects, ledger, n=3)
    assert picked == [b]


def test_compute_backlog_counts_unprocessed(tmp_path):
    from mnemos.auto_refine import compute_backlog

    projects = tmp_path / "projects"
    _write_jsonl(projects, "a.jsonl", 1_000_000)
    _write_jsonl(projects, "b.jsonl", 2_000_000)
    _write_jsonl(projects, "c.jsonl", 3_000_000)

    ledger = tmp_path / "ledger.tsv"
    ledger.write_text(
        f"{projects / 'proj' / 'a.jsonl'}\tOK\tnote.md\n",
        encoding="utf-8",
    )
    assert compute_backlog(projects, ledger) == 2


def test_compute_backlog_zero_when_all_processed(tmp_path):
    from mnemos.auto_refine import compute_backlog

    projects = tmp_path / "projects"
    a = _write_jsonl(projects, "a.jsonl", 1_000_000)

    ledger = tmp_path / "ledger.tsv"
    ledger.write_text(f"{a}\tOK\tnote.md\n", encoding="utf-8")
    assert compute_backlog(projects, ledger) == 0


def test_compute_backlog_no_projects_dir(tmp_path):
    from mnemos.auto_refine import compute_backlog

    assert compute_backlog(tmp_path / "nope", tmp_path / "ledger.tsv") == 0


def test_reminder_shown_on_first_run():
    from datetime import datetime, timezone
    from mnemos.auto_refine import should_show_reminder
    from mnemos.pending import PendingState

    state = PendingState()
    today = datetime(2026, 4, 15, tzinfo=timezone.utc)
    assert should_show_reminder(state, today, backlog=1) is True


def test_reminder_suppressed_within_seven_days():
    from datetime import datetime, timezone
    from mnemos.auto_refine import should_show_reminder
    from mnemos.pending import PendingState

    state = PendingState(backlog_reminder_last_shown="2026-04-13T00:00:00+00:00")
    today = datetime(2026, 4, 15, tzinfo=timezone.utc)  # 2 days later
    assert should_show_reminder(state, today, backlog=1) is False


def test_reminder_shown_after_seven_days():
    from datetime import datetime, timezone
    from mnemos.auto_refine import should_show_reminder
    from mnemos.pending import PendingState

    state = PendingState(backlog_reminder_last_shown="2026-04-01T00:00:00+00:00")
    today = datetime(2026, 4, 15, tzinfo=timezone.utc)  # 14 days later
    assert should_show_reminder(state, today, backlog=1) is True


def test_reminder_suppressed_when_backlog_zero():
    from datetime import datetime, timezone
    from mnemos.auto_refine import should_show_reminder
    from mnemos.pending import PendingState

    state = PendingState()
    today = datetime(2026, 4, 15, tzinfo=timezone.utc)
    assert should_show_reminder(state, today, backlog=0) is False


def test_write_status_creates_file_with_fields(tmp_path):
    import json
    from mnemos.auto_refine import write_status

    write_status(
        vault=tmp_path,
        phase="refining",
        current=1,
        total=3,
        backlog=42,
        reminder_active=True,
        started_at="2026-04-15T14:30:00+00:00",
    )
    data = json.loads((tmp_path / ".mnemos-hook-status.json").read_text(encoding="utf-8"))
    assert data["phase"] == "refining"
    assert data["current"] == 1
    assert data["total"] == 3
    assert data["backlog"] == 42
    assert data["reminder_active"] is True
    assert data["started_at"] == "2026-04-15T14:30:00+00:00"
    assert "updated_at" in data


def test_write_status_overwrites_atomically(tmp_path):
    import json
    from mnemos.auto_refine import write_status

    write_status(tmp_path, "refining", 1, 3, 10, False, "2026-04-15T14:30:00+00:00")
    write_status(tmp_path, "mining", 3, 3, 10, False, "2026-04-15T14:30:00+00:00")
    data = json.loads((tmp_path / ".mnemos-hook-status.json").read_text(encoding="utf-8"))
    assert data["phase"] == "mining"
    assert data["current"] == 3
