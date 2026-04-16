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


def test_run_invokes_refine_for_each_picked_jsonl(tmp_path):
    from mnemos.auto_refine import run

    projects = tmp_path / "projects"
    a = _write_jsonl(projects, "a.jsonl", 1_000_000)
    b = _write_jsonl(projects, "b.jsonl", 2_000_000)

    ledger = tmp_path / "ledger.tsv"
    ledger.touch()

    calls: list[str] = []

    def fake_runner(cmd):
        calls.append(" ".join(str(c) for c in cmd))
        return 0

    run(
        vault=tmp_path,
        projects_dir=projects,
        ledger_path=ledger,
        picked=[b, a],
        reminder_active=False,
        started_at="2026-04-15T14:30:00+00:00",
        runner=fake_runner,
    )

    assert any("/mnemos-refine-transcripts" in c and str(b) in c for c in calls)
    assert any("/mnemos-refine-transcripts" in c and str(a) in c for c in calls)
    assert any("--dangerously-skip-permissions" in c for c in calls)
    assert any("mnemos" in c and "mine" in c for c in calls)
    assert any("-m" in c and "mnemos.cli" in c and "--vault" in c and "mine" in c for c in calls)


def test_run_updates_reminder_timestamp_when_active(tmp_path):
    from mnemos.auto_refine import run
    from mnemos.pending import load, save, PendingState

    projects = tmp_path / "projects"
    ledger = tmp_path / "ledger.tsv"
    ledger.touch()
    save(tmp_path, PendingState())

    def noop_runner(cmd):
        return 0

    run(
        vault=tmp_path,
        projects_dir=projects,
        ledger_path=ledger,
        picked=[],
        reminder_active=True,
        started_at="2026-04-15T14:30:00+00:00",
        runner=noop_runner,
    )
    state = load(tmp_path)
    assert state.backlog_reminder_last_shown is not None


def test_run_sets_phase_idle_when_done(tmp_path):
    import json
    from mnemos.auto_refine import run

    projects = tmp_path / "projects"
    ledger = tmp_path / "ledger.tsv"
    ledger.touch()

    def noop_runner(cmd):
        return 0

    run(
        vault=tmp_path,
        projects_dir=projects,
        ledger_path=ledger,
        picked=[],
        reminder_active=False,
        started_at="2026-04-15T14:30:00+00:00",
        runner=noop_runner,
    )
    data = json.loads((tmp_path / ".mnemos-hook-status.json").read_text(encoding="utf-8"))
    assert data["phase"] == "idle"


def test_pick_recent_excludes_subagent_jsonls(tmp_path):
    from mnemos.auto_refine import pick_recent_jsonls

    projects = tmp_path / "projects"
    # Regular transcript
    regular = projects / "proj" / "sess" / "main.jsonl"
    regular.parent.mkdir(parents=True, exist_ok=True)
    regular.write_text("{}\n", encoding="utf-8")
    os.utime(regular, (2_000_000, 2_000_000))

    # Subagent transcript — should be skipped
    sub = projects / "proj" / "sess" / "subagents" / "agent-abc.jsonl"
    sub.parent.mkdir(parents=True, exist_ok=True)
    sub.write_text("{}\n", encoding="utf-8")
    os.utime(sub, (3_000_000, 3_000_000))  # newer, but filtered

    ledger = tmp_path / "ledger.tsv"
    picked = pick_recent_jsonls(projects, ledger, n=3)
    assert picked == [regular]


def test_compute_backlog_excludes_subagent_jsonls(tmp_path):
    from mnemos.auto_refine import compute_backlog

    projects = tmp_path / "projects"
    (projects / "proj").mkdir(parents=True, exist_ok=True)
    (projects / "proj" / "a.jsonl").write_text("{}\n", encoding="utf-8")
    (projects / "proj" / "subagents").mkdir()
    (projects / "proj" / "subagents" / "x.jsonl").write_text("{}\n", encoding="utf-8")
    (projects / "proj" / "subagents" / "y.jsonl").write_text("{}\n", encoding="utf-8")

    ledger = tmp_path / "ledger.tsv"
    assert compute_backlog(projects, ledger) == 1


# ---------------------------------------------------------------------------
# v0.3 task 3.7c — behavior fixes (lock-silent, skip-empty-mining, outcome fields)
# ---------------------------------------------------------------------------


def test_run_silent_on_lock_timeout_does_not_overwrite_status(tmp_path, monkeypatch):
    """When another worker holds the lock, run() must not touch the status file.

    Previously, lock timeout wrote `phase=busy` which clobbered the lock-holder's
    in-progress state (refining/mining), causing visible flicker.
    """
    import json
    from filelock import Timeout
    from mnemos import auto_refine

    class _BusyLock:
        def __init__(self, *a, **kw): pass
        def __enter__(self): raise Timeout("simulated busy lock")
        def __exit__(self, *a): pass

    monkeypatch.setattr(auto_refine, "FileLock", _BusyLock)

    # Pre-write a "refining" status — should remain untouched after run().
    status_path = tmp_path / ".mnemos-hook-status.json"
    pre_state = {
        "phase": "refining", "current": 2, "total": 3, "backlog": 5,
        "reminder_active": False,
        "started_at": "2026-04-16T10:00:00+00:00",
        "updated_at": "2026-04-16T10:00:30+00:00",
    }
    status_path.write_text(json.dumps(pre_state), encoding="utf-8")

    auto_refine.run(
        vault=tmp_path,
        projects_dir=tmp_path / "projects",
        ledger_path=tmp_path / "ledger.tsv",
        picked=[],
        reminder_active=False,
        started_at="2026-04-16T10:01:00+00:00",
        runner=lambda c: 0,
    )

    after = json.loads(status_path.read_text(encoding="utf-8"))
    assert after == pre_state, "lock timeout must leave the status file untouched"


def test_run_skips_mining_when_no_picked(tmp_path):
    """picked=[] must NOT invoke `mnemos.cli mine` — it's a wasted lock-holding op."""
    from mnemos.auto_refine import run

    projects = tmp_path / "projects"
    ledger = tmp_path / "ledger.tsv"
    ledger.touch()

    calls: list[list[str]] = []

    def recording_runner(cmd):
        calls.append([str(c) for c in cmd])
        return 0

    run(
        vault=tmp_path,
        projects_dir=projects,
        ledger_path=ledger,
        picked=[],
        reminder_active=False,
        started_at="2026-04-16T10:00:00+00:00",
        runner=recording_runner,
    )

    mine_calls = [c for c in calls if "mine" in c]
    assert mine_calls == [], f"runner should not be invoked when picked=[]; got {calls}"


def test_run_still_mines_when_picked_nonempty(tmp_path):
    """Sanity guard: behavior change must not regress the picked>0 case."""
    from mnemos.auto_refine import run

    projects = tmp_path / "projects"
    a = _write_jsonl(projects, "a.jsonl", 1_000_000)
    ledger = tmp_path / "ledger.tsv"
    ledger.touch()

    calls: list[list[str]] = []

    def recording_runner(cmd):
        calls.append([str(c) for c in cmd])
        return 0

    run(
        vault=tmp_path,
        projects_dir=projects,
        ledger_path=ledger,
        picked=[a],
        reminder_active=False,
        started_at="2026-04-16T10:00:00+00:00",
        runner=recording_runner,
    )

    assert any("mine" in c for c in calls), f"mine must still run when picked is non-empty; got {calls}"


def test_run_writes_last_outcome_ok_when_picked(tmp_path):
    """After a successful refine+mine round, idle status must record outcome=ok and timestamp."""
    import json
    from mnemos.auto_refine import run

    projects = tmp_path / "projects"
    a = _write_jsonl(projects, "a.jsonl", 1_000_000)
    ledger = tmp_path / "ledger.tsv"
    ledger.touch()

    run(
        vault=tmp_path,
        projects_dir=projects,
        ledger_path=ledger,
        picked=[a],
        reminder_active=False,
        started_at="2026-04-16T10:00:00+00:00",
        runner=lambda c: 0,
    )

    data = json.loads((tmp_path / ".mnemos-hook-status.json").read_text(encoding="utf-8"))
    assert data["phase"] == "idle"
    assert data["last_outcome"] == "ok"
    assert "last_finished_at" in data and data["last_finished_at"]


def test_run_writes_last_outcome_noop_when_no_picked(tmp_path):
    """picked=[] → idle status must record outcome=noop so the snippet can render 'no-op'."""
    import json
    from mnemos.auto_refine import run

    projects = tmp_path / "projects"
    ledger = tmp_path / "ledger.tsv"
    ledger.touch()

    run(
        vault=tmp_path,
        projects_dir=projects,
        ledger_path=ledger,
        picked=[],
        reminder_active=False,
        started_at="2026-04-16T10:00:00+00:00",
        runner=lambda c: 0,
    )

    data = json.loads((tmp_path / ".mnemos-hook-status.json").read_text(encoding="utf-8"))
    assert data["phase"] == "idle"
    assert data["last_outcome"] == "noop"


def test_write_status_accepts_optional_outcome_fields(tmp_path):
    """write_status() backward-compatible signature: outcome fields are optional kwargs."""
    import json
    from mnemos.auto_refine import write_status

    write_status(
        vault=tmp_path,
        phase="idle",
        current=2,
        total=2,
        backlog=10,
        reminder_active=False,
        started_at="2026-04-16T10:00:00+00:00",
        last_outcome="ok",
        last_finished_at="2026-04-16T10:05:00+00:00",
    )
    data = json.loads((tmp_path / ".mnemos-hook-status.json").read_text(encoding="utf-8"))
    assert data["last_outcome"] == "ok"
    assert data["last_finished_at"] == "2026-04-16T10:05:00+00:00"


# ---------------------------------------------------------------------------
# v0.3 task 3.7d — exclude param on picker (skip in-progress self-transcript)
# ---------------------------------------------------------------------------


def test_pick_recent_jsonls_exclude_path(tmp_path):
    """Picker must skip paths in the `exclude` set even if they are the most recent."""
    from mnemos.auto_refine import pick_recent_jsonls

    projects = tmp_path / "projects"
    a = _write_jsonl(projects, "a.jsonl", 1_000_000)
    b = _write_jsonl(projects, "b.jsonl", 2_000_000)
    self_transcript = _write_jsonl(projects, "self.jsonl", 3_000_000)  # newest, must skip

    ledger = tmp_path / "ledger.tsv"
    picked = pick_recent_jsonls(projects, ledger, n=3, exclude={str(self_transcript)})
    assert picked == [b, a]
    assert self_transcript not in picked


def test_pick_recent_jsonls_exclude_normalises_paths(tmp_path):
    """Exclude set must compare via Path() so backslash/slash differences don't leak."""
    from mnemos.auto_refine import pick_recent_jsonls

    projects = tmp_path / "projects"
    self_transcript = _write_jsonl(projects, "self.jsonl", 3_000_000)

    # Build a string with the opposite separator style to what str(Path) produces.
    raw_path = str(self_transcript)
    twisted = raw_path.replace("\\", "/") if "\\" in raw_path else raw_path.replace("/", "\\")

    ledger = tmp_path / "ledger.tsv"
    picked = pick_recent_jsonls(projects, ledger, n=3, exclude={twisted})
    assert self_transcript not in picked


def test_pick_recent_jsonls_exclude_default_none(tmp_path):
    """exclude=None must behave exactly like the old single-arg call (backward compat)."""
    from mnemos.auto_refine import pick_recent_jsonls

    projects = tmp_path / "projects"
    a = _write_jsonl(projects, "a.jsonl", 1_000_000)
    b = _write_jsonl(projects, "b.jsonl", 2_000_000)
    ledger = tmp_path / "ledger.tsv"
    assert pick_recent_jsonls(projects, ledger, n=3) == [b, a]
    assert pick_recent_jsonls(projects, ledger, n=3, exclude=None) == [b, a]
