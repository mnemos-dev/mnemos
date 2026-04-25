import json
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


def _write_jsonl(projects_dir: Path, name: str, mtime: float, user_turns: int = 3) -> Path:
    """Create a JSONL fixture with `user_turns` real user-typed turns.

    Default 3 turns keeps existing tests above the v0.3 task 3.11 user-turn
    threshold so picker/backlog filters don't quietly exclude fixtures meant
    to test other behavior. Pass `user_turns=0` for empty placeholders.
    """
    path = projects_dir / "proj" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if user_turns <= 0:
        path.write_text("{}\n", encoding="utf-8")
    else:
        lines: list[str] = []
        for i in range(user_turns):
            lines.append(json.dumps({"type": "user", "message": {"role": "user", "content": f"q{i}"}}))
            lines.append(json.dumps({
                "type": "assistant",
                "message": {"role": "assistant", "content": [{"type": "text", "text": f"a{i}"}]},
            }))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
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
    # Regular transcript (with real turns so the v0.3.11 turn-filter doesn't drop it).
    regular = _write_jsonl(projects, "main.jsonl", 2_000_000, user_turns=3)

    # Subagent transcript — should be skipped by path filter regardless of content.
    sub = projects / "proj" / "subagents" / "agent-abc.jsonl"
    sub.parent.mkdir(parents=True, exist_ok=True)
    sub.write_text("{}\n", encoding="utf-8")
    os.utime(sub, (3_000_000, 3_000_000))  # newer, but filtered

    ledger = tmp_path / "ledger.tsv"
    picked = pick_recent_jsonls(projects, ledger, n=3)
    assert picked == [regular]


def test_compute_backlog_excludes_subagent_jsonls(tmp_path):
    """Subagent path filter must exclude under /subagents/ regardless of content.

    Uses min_user_turns=0 so the orthogonal v0.3.11 turn-filter doesn't mask the
    behavior under test (subagent path exclusion). Old mtimes avoid v0.3.12b
    mtime-fallback interference.
    """
    from mnemos.auto_refine import compute_backlog

    projects = tmp_path / "projects"
    (projects / "proj").mkdir(parents=True, exist_ok=True)
    a = projects / "proj" / "a.jsonl"
    a.write_text("{}\n", encoding="utf-8")
    os.utime(a, (1_000_000, 1_000_000))
    (projects / "proj" / "subagents").mkdir()
    sx = projects / "proj" / "subagents" / "x.jsonl"
    sx.write_text("{}\n", encoding="utf-8")
    os.utime(sx, (1_000_000, 1_000_000))
    sy = projects / "proj" / "subagents" / "y.jsonl"
    sy.write_text("{}\n", encoding="utf-8")
    os.utime(sy, (1_000_000, 1_000_000))

    ledger = tmp_path / "ledger.tsv"
    assert compute_backlog(projects, ledger, min_user_turns=0) == 1


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


def test_run_fires_skill_pipeline_when_picked_empty(tmp_path, monkeypatch):
    """Regression for 2026-04-22 incident: `if picked:` gate stranded
    Phase A (unmined Sessions) whenever the refine-picker returned empty
    (e.g. all unprocessed JSONLs belonged to live sessions). Skill mode
    must enter the pipeline regardless of picked."""
    from mnemos.auto_refine import run

    vault = tmp_path
    (vault / "mnemos.yaml").write_text("mine_mode: skill\n", encoding="utf-8")
    (vault / "Sessions").mkdir()
    (vault / "Mnemos").mkdir()
    # One unmined Session md → Phase A will pick it
    session_md = vault / "Sessions" / "2026-04-22-standalone.md"
    session_md.write_text("x", encoding="utf-8")

    projects = tmp_path / "projects"
    projects.mkdir()
    refine_ledger = tmp_path / "refine.tsv"
    refine_ledger.touch()
    mine_ledger = tmp_path / "mine_ledger.tsv"
    mine_ledger.touch()
    monkeypatch.setenv("MNEMOS_MINE_LEDGER", str(mine_ledger))

    calls: list[list[str]] = []

    def recording_runner(cmd):
        calls.append([str(c) for c in cmd])
        if "/mnemos-mine-llm" in cmd[-1]:
            parts = cmd[-1].split()
            with mine_ledger.open("a", encoding="utf-8") as fh:
                fh.write(f"{parts[1]}\t{parts[2]}\t4\t2026-04-22T17:00:00Z\n")
        return 0

    run(
        vault=vault,
        projects_dir=projects,
        ledger_path=refine_ledger,
        picked=[],  # empty — gate under test
        reminder_active=False,
        started_at="2026-04-22T17:00:00+00:00",
        runner=recording_runner,
    )

    # Phase A must have fired for the standalone Session md.
    mine_calls = [c for c in calls if any("/mnemos-mine-llm" in s for s in c)]
    assert len(mine_calls) == 1, (
        f"Phase A mine must fire even when picked=[]; got calls={calls}"
    )
    # Assert the target is our Session md.
    assert "2026-04-22-standalone.md" in " ".join(mine_calls[0])


def test_run_routes_to_skill_pipeline_when_mine_mode_skill(tmp_path, monkeypatch):
    """When mnemos.yaml has mine_mode: skill, hook calls _run_skill_pipeline
    (not the legacy regex `mnemos mine` subprocess)."""
    from mnemos.auto_refine import run

    projects = tmp_path / "projects"
    a = _write_jsonl(projects, "a.jsonl", 1_000_000)
    ledger = tmp_path / "ledger.tsv"
    ledger.touch()
    (tmp_path / "mnemos.yaml").write_text("mine_mode: skill\n", encoding="utf-8")
    (tmp_path / "Sessions").mkdir()
    (tmp_path / "Mnemos").mkdir()
    mine_ledger = tmp_path / "mine_ledger.tsv"
    mine_ledger.touch()
    monkeypatch.setenv("MNEMOS_MINE_LEDGER", str(mine_ledger))

    calls: list[list[str]] = []

    def recording_runner(cmd):
        calls.append([str(c) for c in cmd])
        # Simulate refine OK to enable Phase B chain
        if "/mnemos-refine-transcripts" in cmd[-1]:
            jsonl_path = cmd[-1].split(maxsplit=1)[1]
            name = Path(jsonl_path).stem + ".md"
            (tmp_path / "Sessions" / name).write_text("x", encoding="utf-8")
            with ledger.open("a", encoding="utf-8") as fh:
                fh.write(f"{jsonl_path}\tOK\t{name}\n")
        elif "/mnemos-mine-llm" in cmd[-1]:
            parts = cmd[-1].split()
            with mine_ledger.open("a", encoding="utf-8") as fh:
                fh.write(f"{parts[1]}\t{parts[2]}\t2\t2026-04-22T10:00:00Z\n")
        return 0

    run(
        vault=tmp_path,
        projects_dir=projects,
        ledger_path=ledger,
        picked=[a],
        reminder_active=False,
        started_at="2026-04-22T10:00:00+00:00",
        runner=recording_runner,
    )

    # Legacy regex mine (python -m mnemos.cli ... mine Sessions) must NOT appear.
    assert not any(
        "mnemos.cli" in " ".join(c) and "mine" in c for c in calls
    ), f"legacy regex mine still firing: {calls}"
    # But /mnemos-refine-transcripts AND /mnemos-mine-llm must appear.
    assert any("/mnemos-refine-transcripts" in " ".join(c) for c in calls)
    assert any("/mnemos-mine-llm" in " ".join(c) for c in calls)


def test_read_mine_mode_defaults_to_script_when_yaml_missing(tmp_path):
    from mnemos.auto_refine import _read_mine_mode

    assert _read_mine_mode(tmp_path) == "script"


def test_read_mine_mode_parses_yaml_value(tmp_path):
    from mnemos.auto_refine import _read_mine_mode

    (tmp_path / "mnemos.yaml").write_text(
        "search_backend: sqlite-vec\nmine_mode: skill\nother: x\n", encoding="utf-8"
    )
    assert _read_mine_mode(tmp_path) == "skill"

    (tmp_path / "mnemos.yaml").write_text("mine_mode: 'script'\n", encoding="utf-8")
    assert _read_mine_mode(tmp_path) == "script"


def test_run_writes_last_outcome_ok_when_picked(tmp_path):
    """After a refine round that actually produces ≥1 OK note, idle records outcome=ok.

    Updated for v0.3.11 semantics: 'ok' now requires the skill to have written
    an OK ledger row (the prior 'picked nonempty → ok' contract was the lie that
    showed "3 notes · OK · backlog 150" when 0 notes were actually created).
    """
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
        runner=_ledger_writing_runner(ledger, {a: "OK"}),
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


# ---------------------------------------------------------------------------
# v0.3 task 3.11 — user-turn filter + accurate OK/SKIP status reporting
# ---------------------------------------------------------------------------


def test_min_user_turns_default_is_three():
    """The shipped threshold is 3 — sessions with fewer turns are noise (resume-only)."""
    from mnemos.auto_refine import MIN_USER_TURNS
    assert MIN_USER_TURNS == 3


def test_count_user_turns_minimal_session(tmp_path):
    """One real user message → count 1."""
    from mnemos.auto_refine import _count_user_turns
    p = tmp_path / "x.jsonl"
    p.write_text(
        json.dumps({"type": "user", "message": {"role": "user", "content": "hello"}}) + "\n"
        + json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "hi"}]}}) + "\n",
        encoding="utf-8",
    )
    assert _count_user_turns(p) == 1


def test_count_user_turns_excludes_tool_results(tmp_path):
    """Tool result messages have type=user but must NOT be counted as turns.

    Without this, a 1-turn session with heavy tool use would falsely register
    as N turns and bypass the noise filter.
    """
    from mnemos.auto_refine import _count_user_turns
    p = tmp_path / "x.jsonl"
    p.write_text(
        json.dumps({"type": "user", "message": {"role": "user", "content": "do thing"}}) + "\n"
        + json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "X", "input": {}}]}}) + "\n"
        + json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "done"}]}}) + "\n"
        + json.dumps({"type": "user", "message": {"role": "user", "content": "thanks"}}) + "\n",
        encoding="utf-8",
    )
    assert _count_user_turns(p) == 2


def test_count_user_turns_handles_missing_file(tmp_path):
    from mnemos.auto_refine import _count_user_turns
    assert _count_user_turns(tmp_path / "nope.jsonl") == 0


def test_count_user_turns_tolerates_malformed_lines(tmp_path):
    """Malformed JSON / blank lines are skipped, not raised."""
    from mnemos.auto_refine import _count_user_turns
    p = tmp_path / "x.jsonl"
    p.write_text(
        "not-json\n"
        + json.dumps({"type": "user", "message": {"role": "user", "content": "a"}}) + "\n"
        + "\n"
        + "{}\n"
        + json.dumps({"type": "user", "message": {"role": "user", "content": "b"}}) + "\n",
        encoding="utf-8",
    )
    assert _count_user_turns(p) == 2


def test_pick_recent_filters_short_transcripts_by_default(tmp_path):
    """A 1-turn JSONL must NOT be picked even if it's the newest."""
    from mnemos.auto_refine import pick_recent_jsonls

    projects = tmp_path / "projects"
    short = _write_jsonl(projects, "short.jsonl", 3_000_000, user_turns=1)  # newest, too short
    real = _write_jsonl(projects, "real.jsonl", 2_000_000, user_turns=5)
    ledger = tmp_path / "ledger.tsv"

    picked = pick_recent_jsonls(projects, ledger, n=3)  # default min_user_turns=3
    assert short not in picked
    assert real in picked


def test_pick_recent_filter_threshold_boundary(tmp_path):
    """Exactly min_user_turns is accepted (>=, not >)."""
    from mnemos.auto_refine import pick_recent_jsonls

    projects = tmp_path / "projects"
    edge = _write_jsonl(projects, "edge.jsonl", 1_000_000, user_turns=3)
    ledger = tmp_path / "ledger.tsv"

    assert edge in pick_recent_jsonls(projects, ledger, n=3, min_user_turns=3)


def test_pick_recent_min_turns_zero_disables_filter(tmp_path):
    """min_user_turns=0 = explicit opt-out (used by tests of orthogonal behavior)."""
    from mnemos.auto_refine import pick_recent_jsonls

    projects = tmp_path / "projects"
    short = _write_jsonl(projects, "short.jsonl", 1_000_000, user_turns=1)
    ledger = tmp_path / "ledger.tsv"

    assert short in pick_recent_jsonls(projects, ledger, n=3, min_user_turns=0)


def test_compute_backlog_filters_short_transcripts(tmp_path):
    """Short transcripts vanish from the visible backlog (the user's real complaint:
    150-backlog stayed flat because every fire wasted picks on noise files)."""
    from mnemos.auto_refine import compute_backlog

    projects = tmp_path / "projects"
    _write_jsonl(projects, "short1.jsonl", 1_000_000, user_turns=1)
    _write_jsonl(projects, "short2.jsonl", 1_500_000, user_turns=2)
    _write_jsonl(projects, "real.jsonl", 2_000_000, user_turns=5)
    ledger = tmp_path / "ledger.tsv"

    assert compute_backlog(projects, ledger) == 1


def test_write_status_accepts_last_ok_and_last_skip(tmp_path):
    """Status payload must carry per-round OK/SKIP counts so the snippet renders truthfully."""
    from mnemos.auto_refine import write_status

    write_status(
        vault=tmp_path,
        phase="idle",
        current=3, total=3, backlog=10,
        reminder_active=False,
        started_at="2026-04-16T10:00:00+00:00",
        last_outcome="skip",
        last_finished_at="2026-04-16T10:05:00+00:00",
        last_ok=0, last_skip=3,
    )
    data = json.loads((tmp_path / ".mnemos-hook-status.json").read_text(encoding="utf-8"))
    assert data["last_ok"] == 0
    assert data["last_skip"] == 3
    assert data["last_outcome"] == "skip"


def test_write_status_omits_outcome_counts_when_unset(tmp_path):
    """Backward compat: if caller doesn't pass last_ok/last_skip, JSON omits them."""
    from mnemos.auto_refine import write_status

    write_status(
        vault=tmp_path,
        phase="refining",
        current=1, total=2, backlog=5,
        reminder_active=False,
        started_at="2026-04-16T10:00:00+00:00",
    )
    data = json.loads((tmp_path / ".mnemos-hook-status.json").read_text(encoding="utf-8"))
    assert "last_ok" not in data
    assert "last_skip" not in data


def _ledger_writing_runner(ledger: Path, outcomes: dict[Path, str]):
    """Build a fake runner that simulates refine-skill writing OK/SKIP rows.

    `outcomes` maps each picked path to the status the skill would record.
    The mine call is treated as a no-op.
    """
    def runner(cmd):
        cmd_str = " ".join(str(c) for c in cmd)
        if "/mnemos-refine-transcripts" not in cmd_str:
            return 0
        for path, status in outcomes.items():
            if str(path) in cmd_str:
                with ledger.open("a", encoding="utf-8") as fh:
                    note = "note.md" if status == "OK" else "skipped"
                    fh.write(f"{path}\t{status}\t{note}\n")
                return 0
        return 0
    return runner


def test_run_records_last_ok_and_last_skip_from_ledger_delta(tmp_path):
    """After a round, status.last_ok / last_skip reflect what the skill actually wrote."""
    from mnemos.auto_refine import run

    projects = tmp_path / "projects"
    a = _write_jsonl(projects, "a.jsonl", 1_000_000, user_turns=5)
    b = _write_jsonl(projects, "b.jsonl", 2_000_000, user_turns=5)
    ledger = tmp_path / "ledger.tsv"
    ledger.touch()

    run(
        vault=tmp_path,
        projects_dir=projects,
        ledger_path=ledger,
        picked=[a, b],
        reminder_active=False,
        started_at="2026-04-16T10:00:00+00:00",
        runner=_ledger_writing_runner(ledger, {a: "OK", b: "SKIP"}),
    )

    data = json.loads((tmp_path / ".mnemos-hook-status.json").read_text(encoding="utf-8"))
    assert data["last_ok"] == 1
    assert data["last_skip"] == 1


def test_run_last_outcome_skip_when_all_picked_were_skipped(tmp_path):
    """All picks SKIP → outcome must be 'skip', NOT the misleading 'ok' that v0.3.7c shipped.

    This is the user's primary complaint surface: statusline showed
    '3 notes · OK' when actually 0 notes were created (all 3 SKIP).
    """
    from mnemos.auto_refine import run

    projects = tmp_path / "projects"
    a = _write_jsonl(projects, "a.jsonl", 1_000_000, user_turns=5)
    ledger = tmp_path / "ledger.tsv"
    ledger.touch()

    run(
        vault=tmp_path,
        projects_dir=projects,
        ledger_path=ledger,
        picked=[a],
        reminder_active=False,
        started_at="2026-04-16T10:00:00+00:00",
        runner=_ledger_writing_runner(ledger, {a: "SKIP"}),
    )

    data = json.loads((tmp_path / ".mnemos-hook-status.json").read_text(encoding="utf-8"))
    assert data["last_outcome"] == "skip"
    assert data["last_ok"] == 0
    assert data["last_skip"] == 1


def test_run_last_outcome_ok_when_at_least_one_real_note(tmp_path):
    """≥1 OK across the round → outcome=ok (preserves prior semantics for non-mixed rounds)."""
    from mnemos.auto_refine import run

    projects = tmp_path / "projects"
    a = _write_jsonl(projects, "a.jsonl", 1_000_000, user_turns=5)
    b = _write_jsonl(projects, "b.jsonl", 2_000_000, user_turns=5)
    ledger = tmp_path / "ledger.tsv"
    ledger.touch()

    run(
        vault=tmp_path,
        projects_dir=projects,
        ledger_path=ledger,
        picked=[a, b],
        reminder_active=False,
        started_at="2026-04-16T10:00:00+00:00",
        runner=_ledger_writing_runner(ledger, {a: "OK", b: "SKIP"}),
    )

    data = json.loads((tmp_path / ".mnemos-hook-status.json").read_text(encoding="utf-8"))
    assert data["last_outcome"] == "ok"


def test_run_last_outcome_noop_when_picked_empty(tmp_path):
    """picked=[] → outcome=noop (regression guard for v0.3.7c semantics)."""
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
    assert data["last_outcome"] == "noop"


# ---------------------------------------------------------------------------
# v0.3 task 3.12 — PID-based active-session exclusion
# ---------------------------------------------------------------------------


def test_is_pid_alive_for_current_process():
    """Our own PID must always be reported alive."""
    from mnemos.auto_refine import _is_pid_alive
    assert _is_pid_alive(os.getpid()) is True


def test_is_pid_alive_for_dead_pid():
    """A PID that doesn't exist must report dead."""
    from mnemos.auto_refine import _is_pid_alive
    # PID 0 is special (kernel); use a very high PID that's almost certainly unused.
    assert _is_pid_alive(4_000_000) is False


def test_register_active_session_creates_marker(tmp_path):
    """Registering a session writes a JSON marker under .mnemos-active-sessions/."""
    from mnemos.auto_refine import ACTIVE_SESSIONS_DIR, register_active_session

    register_active_session(
        sessions_dir=tmp_path / ACTIVE_SESSIONS_DIR,
        session_id="abc-123",
        transcript_path="/some/path.jsonl",
        pid=os.getpid(),
    )
    marker = tmp_path / ACTIVE_SESSIONS_DIR / "abc-123.json"
    assert marker.exists()
    data = json.loads(marker.read_text(encoding="utf-8"))
    assert data["pid"] == os.getpid()
    assert data["transcript_path"] == "/some/path.jsonl"
    assert "started_at" in data


def test_get_active_transcript_paths_returns_live_pids(tmp_path):
    """Active sessions (PID alive) must appear in the returned set."""
    from mnemos.auto_refine import (
        ACTIVE_SESSIONS_DIR,
        get_active_transcript_paths,
        register_active_session,
    )

    sessions_dir = tmp_path / ACTIVE_SESSIONS_DIR
    register_active_session(sessions_dir, "s1", "/a.jsonl", os.getpid())
    result = get_active_transcript_paths(sessions_dir)
    assert "/a.jsonl" in result


def test_get_active_transcript_paths_removes_dead_pids(tmp_path):
    """Dead PIDs must be cleaned up and excluded from the result."""
    from mnemos.auto_refine import ACTIVE_SESSIONS_DIR, get_active_transcript_paths

    sessions_dir = tmp_path / ACTIVE_SESSIONS_DIR
    sessions_dir.mkdir(parents=True, exist_ok=True)
    marker = sessions_dir / "dead-session.json"
    marker.write_text(json.dumps({
        "pid": 4_000_000,  # dead
        "transcript_path": "/dead.jsonl",
        "started_at": "2026-04-17T00:00:00+00:00",
    }), encoding="utf-8")

    result = get_active_transcript_paths(sessions_dir)
    assert "/dead.jsonl" not in result
    assert not marker.exists(), "dead PID marker must be cleaned up"


def test_get_active_transcript_paths_removes_stale_markers(tmp_path):
    """Markers older than 24h must be removed regardless of PID liveness (PID recycling guard)."""
    from mnemos.auto_refine import ACTIVE_SESSIONS_DIR, get_active_transcript_paths

    sessions_dir = tmp_path / ACTIVE_SESSIONS_DIR
    sessions_dir.mkdir(parents=True, exist_ok=True)
    marker = sessions_dir / "stale.json"
    marker.write_text(json.dumps({
        "pid": os.getpid(),  # alive — but marker is stale
        "transcript_path": "/stale.jsonl",
        "started_at": "2026-04-14T00:00:00+00:00",  # 3 days ago
    }), encoding="utf-8")

    result = get_active_transcript_paths(sessions_dir)
    assert "/stale.jsonl" not in result
    assert not marker.exists()


def test_get_active_transcript_paths_empty_dir(tmp_path):
    """Non-existent or empty sessions dir → empty set, no crash."""
    from mnemos.auto_refine import get_active_transcript_paths
    assert get_active_transcript_paths(tmp_path / "nope") == set()


def test_pick_recent_excludes_active_sessions(tmp_path):
    """Picker must not return JSONLs that belong to currently-active sessions."""
    from mnemos.auto_refine import pick_recent_jsonls

    projects = tmp_path / "projects"
    closed = _write_jsonl(projects, "closed.jsonl", 1_000_000, user_turns=5)
    active = _write_jsonl(projects, "active.jsonl", 2_000_000, user_turns=5)
    ledger = tmp_path / "ledger.tsv"

    active_paths = {str(active)}
    picked = pick_recent_jsonls(projects, ledger, n=3, exclude=active_paths)
    assert active not in picked
    assert closed in picked


def test_compute_backlog_excludes_active_sessions(tmp_path):
    """Active sessions must NOT inflate the backlog count (they're not 'available to process')."""
    from mnemos.auto_refine import compute_backlog

    projects = tmp_path / "projects"
    _write_jsonl(projects, "closed.jsonl", 1_000_000, user_turns=5)
    active = _write_jsonl(projects, "active.jsonl", 2_000_000, user_turns=5)
    ledger = tmp_path / "ledger.tsv"

    assert compute_backlog(projects, ledger, active_paths={str(active)}) == 1


def test_compute_backlog_no_active_paths_backward_compat(tmp_path):
    """active_paths=None means no exclusion (backward compat)."""
    from mnemos.auto_refine import compute_backlog

    projects = tmp_path / "projects"
    _write_jsonl(projects, "a.jsonl", 1_000_000, user_turns=5)
    _write_jsonl(projects, "b.jsonl", 2_000_000, user_turns=5)
    ledger = tmp_path / "ledger.tsv"

    assert compute_backlog(projects, ledger) == 2


# ---------------------------------------------------------------------------
# v0.3 task 3.12b — mtime fallback for pre-existing sessions + wrapper guard
# ---------------------------------------------------------------------------


def test_pick_recent_skips_recently_modified_unmarked_jsonl(tmp_path):
    """A JSONL modified within RECENTLY_MODIFIED_SECONDS and NOT in active_paths
    must be skipped — it's likely an open session that predates 3.12 PID markers.

    This is the fallback that prevents refining a session whose window was open
    before 3.12 was deployed (no marker yet, but mtime proves it's being written).
    """
    import time
    from mnemos.auto_refine import pick_recent_jsonls

    projects = tmp_path / "projects"
    # `old` has a stale mtime — safe to pick
    old = _write_jsonl(projects, "old.jsonl", 1_000_000, user_turns=5)
    # `hot` has mtime = NOW — looks like it's being actively written
    hot = _write_jsonl(projects, "hot.jsonl", time.time(), user_turns=5)
    ledger = tmp_path / "ledger.tsv"

    # No active_paths marker for `hot`, but mtime fallback should catch it
    picked = pick_recent_jsonls(projects, ledger, n=3, exclude=set())
    assert hot not in picked, "recently-modified unmarked JSONL must be skipped as likely-active"
    assert old in picked


def test_pick_recent_mtime_fallback_does_not_apply_when_marker_exists(tmp_path):
    """If a JSONL IS in active_paths (has a PID marker), mtime is irrelevant —
    the PID check already handles it. The mtime fallback only matters for
    UNmarked files whose mtime is recent.
    """
    import time
    from mnemos.auto_refine import pick_recent_jsonls

    projects = tmp_path / "projects"
    # Old mtime but in active_paths → excluded by active_paths, not mtime
    old_active = _write_jsonl(projects, "old_active.jsonl", 1_000_000, user_turns=5)
    ledger = tmp_path / "ledger.tsv"

    picked = pick_recent_jsonls(projects, ledger, n=3, exclude={str(old_active)})
    assert old_active not in picked


def test_compute_backlog_skips_recently_modified(tmp_path):
    """Backlog must not count recently-modified unmarked JSONLs (same logic as picker)."""
    import time
    from mnemos.auto_refine import compute_backlog

    projects = tmp_path / "projects"
    _write_jsonl(projects, "old.jsonl", 1_000_000, user_turns=5)
    _write_jsonl(projects, "hot.jsonl", time.time(), user_turns=5)
    ledger = tmp_path / "ledger.tsv"

    assert compute_backlog(projects, ledger, active_paths=set()) == 1


def test_read_status_phase(tmp_path):
    """read_status_phase returns the current phase from the status file."""
    from mnemos.auto_refine import read_status_phase, write_status

    assert read_status_phase(tmp_path) is None  # no file yet
    write_status(tmp_path, "refining", 1, 3, 10, False, "2026-04-17T00:00:00+00:00")
    assert read_status_phase(tmp_path) == "refining"
    write_status(tmp_path, "idle", 3, 3, 10, False, "2026-04-17T00:00:00+00:00")
    assert read_status_phase(tmp_path) == "idle"


# ---------------------------------------------------------------------------
# v0.3 task 3.12c — per-session statusline (triggering_session_id)
# ---------------------------------------------------------------------------


def test_write_status_includes_triggering_session_id(tmp_path):
    """Status JSON must carry the triggering session's ID so the snippet can
    filter: only the session that fired the hook sees the progress."""
    from mnemos.auto_refine import write_status

    write_status(
        tmp_path, "refining", 0, 3, 10, False, "2026-04-17T00:00:00+00:00",
        triggering_session_id="abc-123",
    )
    data = json.loads((tmp_path / ".mnemos-hook-status.json").read_text(encoding="utf-8"))
    assert data["triggering_session_id"] == "abc-123"


def test_write_status_omits_triggering_session_id_when_unset(tmp_path):
    """Backward compat: if not passed, field absent from JSON."""
    from mnemos.auto_refine import write_status

    write_status(tmp_path, "refining", 0, 3, 10, False, "2026-04-17T00:00:00+00:00")
    data = json.loads((tmp_path / ".mnemos-hook-status.json").read_text(encoding="utf-8"))
    assert "triggering_session_id" not in data


def test_run_passes_triggering_session_id_through_to_status(tmp_path):
    """_run_locked must propagate triggering_session_id to every write_status call
    so the snippet can filter throughout the entire refine+mine cycle."""
    from mnemos.auto_refine import run

    projects = tmp_path / "projects"
    a = _write_jsonl(projects, "a.jsonl", 1_000_000, user_turns=5)
    ledger = tmp_path / "ledger.tsv"
    ledger.touch()

    run(
        vault=tmp_path,
        projects_dir=projects,
        ledger_path=ledger,
        picked=[a],
        reminder_active=False,
        started_at="2026-04-17T00:00:00+00:00",
        runner=_ledger_writing_runner(ledger, {a: "OK"}),
        triggering_session_id="my-session-xyz",
    )

    data = json.loads((tmp_path / ".mnemos-hook-status.json").read_text(encoding="utf-8"))
    assert data.get("triggering_session_id") == "my-session-xyz"


def test_pick_unprocessed_jsonls_returns_all_under_limit(tmp_path):
    from mnemos.auto_refine import _pick_unprocessed_jsonls

    projects = tmp_path / "projects"
    # Create 5 fresh JSONLs, none in ledger
    old = 1_000_000
    paths = [_write_jsonl(projects, f"s{i}.jsonl", old + i) for i in range(5)]
    ledger = tmp_path / "ledger.tsv"
    ledger.touch()

    picked = _pick_unprocessed_jsonls(
        projects_dir=projects, ledger_path=ledger, limit=10,
        exclude=set(), active_paths=set(),
    )
    assert len(picked) == 5
    # mtime desc order — s4 newest
    assert picked[0].name == "s4.jsonl"


def test_pick_unprocessed_jsonls_honors_limit(tmp_path):
    from mnemos.auto_refine import _pick_unprocessed_jsonls

    projects = tmp_path / "projects"
    for i in range(7):
        _write_jsonl(projects, f"s{i}.jsonl", 1_000_000 + i)
    ledger = tmp_path / "ledger.tsv"
    ledger.touch()

    picked = _pick_unprocessed_jsonls(
        projects_dir=projects, ledger_path=ledger, limit=3,
        exclude=set(), active_paths=set(),
    )
    assert len(picked) == 3


def test_pick_unmined_sessions_returns_unmined(tmp_path):
    from mnemos.auto_refine import _pick_unmined_sessions

    vault = tmp_path
    sessions = vault / "Sessions"
    sessions.mkdir()
    (sessions / "2026-04-20-a.md").write_text("x", encoding="utf-8")
    (sessions / "2026-04-21-b.md").write_text("x", encoding="utf-8")
    (sessions / "2026-04-22-c.md").write_text("x", encoding="utf-8")
    # Mine ledger: only b.md processed
    mine_ledger = tmp_path / "mined.tsv"
    palace = str(vault / "Mnemos")
    mine_ledger.write_text(
        f"{sessions / '2026-04-21-b.md'}\t{palace}\t3\t2026-04-21T10:00:00Z\n",
        encoding="utf-8",
    )

    picked = _pick_unmined_sessions(
        vault=vault, mine_ledger_path=mine_ledger,
        palace_root=vault / "Mnemos", limit=10,
    )
    names = {p.name for p in picked}
    assert names == {"2026-04-20-a.md", "2026-04-22-c.md"}


def test_pick_unmined_sessions_honors_limit(tmp_path):
    from mnemos.auto_refine import _pick_unmined_sessions

    sessions = tmp_path / "Sessions"
    sessions.mkdir()
    for i in range(5):
        (sessions / f"2026-04-2{i}-s.md").write_text("x", encoding="utf-8")
    mine_ledger = tmp_path / "mined.tsv"
    mine_ledger.touch()

    picked = _pick_unmined_sessions(
        vault=tmp_path, mine_ledger_path=mine_ledger,
        palace_root=tmp_path / "Mnemos", limit=2,
    )
    assert len(picked) == 2


def test_latest_session_for_jsonl_returns_path(tmp_path):
    from mnemos.auto_refine import _latest_session_for_jsonl

    vault = tmp_path
    (vault / "Sessions").mkdir()
    ledger = tmp_path / "refine.tsv"
    jsonl = tmp_path / "proj" / "abc.jsonl"
    ledger.write_text(
        f"{jsonl}\tOK\t2026-04-22-abc.md\n",
        encoding="utf-8",
    )

    result = _latest_session_for_jsonl(ledger, jsonl, vault)
    assert result == ("OK", vault / "Sessions" / "2026-04-22-abc.md")


def test_latest_session_for_jsonl_missing_returns_none(tmp_path):
    from mnemos.auto_refine import _latest_session_for_jsonl

    ledger = tmp_path / "refine.tsv"
    ledger.touch()
    result = _latest_session_for_jsonl(ledger, tmp_path / "x.jsonl", tmp_path)
    assert result is None


def test_run_skill_pipeline_phase_a_only(tmp_path, monkeypatch):
    """When there are unmined Sessions but no unrefined JSONLs, only Phase A runs."""
    from mnemos.auto_refine import _run_skill_pipeline

    vault = tmp_path
    (vault / "Sessions").mkdir()
    (vault / "Mnemos").mkdir()
    # Two Sessions, neither in mine ledger
    (vault / "Sessions" / "2026-04-21-a.md").write_text("x", encoding="utf-8")
    (vault / "Sessions" / "2026-04-22-b.md").write_text("x", encoding="utf-8")
    mine_ledger = tmp_path / "mined.tsv"
    mine_ledger.touch()
    refine_ledger = tmp_path / "refine.tsv"
    refine_ledger.touch()
    projects = tmp_path / "projects"
    projects.mkdir()

    calls: list[list[str]] = []

    def fake_runner(cmd):
        calls.append([str(c) for c in cmd])
        # Simulate mine OK — append to mine_ledger
        if "/mnemos-mine-llm" in cmd[-1]:
            parts = cmd[-1].split()
            session_path = parts[1]
            palace = parts[2]
            with mine_ledger.open("a", encoding="utf-8") as fh:
                fh.write(f"{session_path}\t{palace}\t3\t2026-04-22T10:00:00Z\n")
        return 0

    _run_skill_pipeline(
        vault=vault, projects_dir=projects,
        refine_ledger_path=refine_ledger, mine_ledger_path=mine_ledger,
        runner=fake_runner, cap=10,
    )

    # Two /mnemos-mine-llm calls, no /mnemos-refine-transcripts
    mine_calls = [c for c in calls if any("/mnemos-mine-llm" in s for s in c)]
    refine_calls = [c for c in calls if any("/mnemos-refine-transcripts" in s for s in c)]
    assert len(mine_calls) == 2
    assert refine_calls == []


def test_run_skill_pipeline_cap_allocation(tmp_path):
    """Phase A fills cap first; remaining slots go to Phase B."""
    from mnemos.auto_refine import _run_skill_pipeline

    vault = tmp_path
    (vault / "Sessions").mkdir()
    (vault / "Mnemos").mkdir()
    # 7 unmined Sessions + 15 unrefined JSONLs + cap=10 ⇒ 7 Phase A + 3 Phase B.
    for i in range(7):
        (vault / "Sessions" / f"2026-04-1{i}-s.md").write_text("x", encoding="utf-8")
    mine_ledger = tmp_path / "mined.tsv"
    mine_ledger.touch()
    refine_ledger = tmp_path / "refine.tsv"
    refine_ledger.touch()
    projects = tmp_path / "projects"
    for i in range(15):
        _write_jsonl(projects, f"s{i}.jsonl", 1_000_000 + i)

    calls: list[str] = []

    def fake_runner(cmd):
        calls.append(cmd[-1])
        if "/mnemos-refine-transcripts" in cmd[-1]:
            jsonl_path = cmd[-1].split(maxsplit=1)[1]
            name = Path(jsonl_path).stem + ".md"
            (vault / "Sessions" / name).write_text("x", encoding="utf-8")
            with refine_ledger.open("a", encoding="utf-8") as fh:
                fh.write(f"{jsonl_path}\tOK\t{name}\n")
        elif "/mnemos-mine-llm" in cmd[-1]:
            parts = cmd[-1].split()
            with mine_ledger.open("a", encoding="utf-8") as fh:
                fh.write(f"{parts[1]}\t{parts[2]}\t1\t2026-04-22T10:00:00Z\n")
        return 0

    _run_skill_pipeline(
        vault=vault, projects_dir=projects,
        refine_ledger_path=refine_ledger, mine_ledger_path=mine_ledger,
        runner=lambda c: fake_runner(c), cap=10,
    )

    # Phase A = 7 mine calls; Phase B = 3 JSONL × (1 refine + 1 mine) = 6 calls.
    # Total: 7 + 6 = 13 subprocess invocations.
    refine_calls = [c for c in calls if "/mnemos-refine-transcripts" in c]
    mine_calls = [c for c in calls if "/mnemos-mine-llm" in c]
    assert len(refine_calls) == 3
    assert len(mine_calls) == 7 + 3  # A + B
