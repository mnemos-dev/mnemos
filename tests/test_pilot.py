"""Tests for mnemos.pilot — skill-mine pilot orchestrator."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mnemos.pilot import (
    PilotError,
    PilotPlan,
    PilotResult,
    RunnerResult,
    SessionOutcome,
    TokenUsage,
    build_plan,
    format_pilot_report,
    parse_claude_json_output,
    read_ledger_entry,
    run_pilot,
    sessions_needing_run,
    write_pilot_report,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(sessions_dir: Path, name: str, *, mtime: float | None = None) -> Path:
    sessions_dir.mkdir(parents=True, exist_ok=True)
    p = sessions_dir / name
    p.write_text("---\ndate: 2026-04-19\nproject: Mnemos\n---\n\n# Test\n", encoding="utf-8")
    if mtime is not None:
        import os
        os.utime(p, (mtime, mtime))
    return p


def _write_ledger_row(ledger: Path, session: Path, palace: Path, drawers: int, marker: str) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(f"{session}\t{palace}\t{drawers}\t{marker}\n")


# ---------------------------------------------------------------------------
# build_plan
# ---------------------------------------------------------------------------


def test_build_plan_discovers_sessions_newest_first(tmp_path: Path) -> None:
    sdir = tmp_path / "Sessions"
    _make_session(sdir, "2026-04-10-old.md", mtime=time.time() - 86400 * 10)
    recent = _make_session(sdir, "2026-04-18-recent.md", mtime=time.time() - 60)
    middle = _make_session(sdir, "2026-04-15-middle.md", mtime=time.time() - 3600)

    plan = build_plan(tmp_path, limit=10)

    assert plan.session_count == 3
    assert plan.sessions[0] == recent
    assert plan.sessions[1] == middle


def test_build_plan_respects_limit(tmp_path: Path) -> None:
    sdir = tmp_path / "Sessions"
    for i in range(20):
        _make_session(sdir, f"2026-04-{i+1:02d}-s.md", mtime=time.time() - i)

    plan = build_plan(tmp_path, limit=5)
    assert plan.session_count == 5


def test_build_plan_raises_without_sessions_dir(tmp_path: Path) -> None:
    with pytest.raises(PilotError, match="No refined sessions"):
        build_plan(tmp_path)


def test_build_plan_raises_with_empty_sessions_dir(tmp_path: Path) -> None:
    (tmp_path / "Sessions").mkdir()
    with pytest.raises(PilotError, match="No refined sessions"):
        build_plan(tmp_path)


def test_build_plan_raises_for_bad_vault(tmp_path: Path) -> None:
    missing = tmp_path / "nonexistent"
    with pytest.raises(PilotError, match="Vault path does not exist"):
        build_plan(missing)


def test_build_plan_rejects_zero_limit(tmp_path: Path) -> None:
    _make_session(tmp_path / "Sessions", "s.md")
    with pytest.raises(PilotError, match="limit must be >= 1"):
        build_plan(tmp_path, limit=0)


def test_build_plan_computes_palace_paths(tmp_path: Path) -> None:
    _make_session(tmp_path / "Sessions", "s.md")
    plan = build_plan(tmp_path)
    assert plan.script_palace == tmp_path / "Mnemos"
    assert plan.skill_palace == tmp_path / "Mnemos-pilot"


# ---------------------------------------------------------------------------
# parse_claude_json_output
# ---------------------------------------------------------------------------


def test_parse_claude_json_output_extracts_usage() -> None:
    stdout = json.dumps({
        "type": "result",
        "subtype": "success",
        "result": "OK refined.md → 5 drawers",
        "usage": {
            "input_tokens": 3200,
            "output_tokens": 850,
            "cache_read_input_tokens": 1100,
            "cache_creation_input_tokens": 0,
        },
    })
    text, usage = parse_claude_json_output(stdout)
    assert "5 drawers" in text
    assert usage.input_tokens == 3200
    assert usage.output_tokens == 850
    assert usage.cache_read_input_tokens == 1100
    assert usage.total() == 3200 + 850 + 1100


def test_parse_claude_json_output_handles_empty() -> None:
    text, usage = parse_claude_json_output("")
    assert text == ""
    assert usage.total() == 0


def test_parse_claude_json_output_handles_malformed_json() -> None:
    text, usage = parse_claude_json_output("not json at all")
    assert text == ""
    assert usage.total() == 0


def test_parse_claude_json_output_handles_missing_usage() -> None:
    stdout = json.dumps({"type": "result", "result": "OK"})
    text, usage = parse_claude_json_output(stdout)
    assert text == "OK"
    assert usage.total() == 0


# ---------------------------------------------------------------------------
# TokenUsage
# ---------------------------------------------------------------------------


def test_token_usage_add() -> None:
    a = TokenUsage(input_tokens=10, output_tokens=5)
    b = TokenUsage(input_tokens=3, output_tokens=2, cache_read_input_tokens=7)
    a.add(b)
    assert a.input_tokens == 13
    assert a.output_tokens == 7
    assert a.cache_read_input_tokens == 7
    assert a.total() == 13 + 7 + 7


# ---------------------------------------------------------------------------
# read_ledger_entry
# ---------------------------------------------------------------------------


def test_read_ledger_entry_returns_none_for_missing_file(tmp_path: Path) -> None:
    result = read_ledger_entry(
        tmp_path / "nope.tsv", tmp_path / "s.md", tmp_path / "Mnemos-pilot"
    )
    assert result is None


def test_read_ledger_entry_matches_ok_row(tmp_path: Path) -> None:
    ledger = tmp_path / "mined.tsv"
    session = tmp_path / "Sessions" / "s.md"
    palace = tmp_path / "Mnemos-pilot"
    _write_ledger_row(ledger, session, palace, 5, "2026-04-19T10:00:00Z")

    entry = read_ledger_entry(ledger, session, palace)
    assert entry is not None
    outcome, count, reason = entry
    assert outcome == "ok"
    assert count == 5
    assert reason == ""


def test_read_ledger_entry_parses_skip_row(tmp_path: Path) -> None:
    ledger = tmp_path / "mined.tsv"
    session = tmp_path / "s.md"
    palace = tmp_path / "P"
    _write_ledger_row(ledger, session, palace, 0, "SKIP: only todo list")

    entry = read_ledger_entry(ledger, session, palace)
    assert entry is not None
    outcome, count, reason = entry
    assert outcome == "skip"
    assert count == 0
    assert reason == "only todo list"


def test_read_ledger_entry_returns_latest_when_multiple_rows(tmp_path: Path) -> None:
    ledger = tmp_path / "mined.tsv"
    session = tmp_path / "s.md"
    palace = tmp_path / "P"
    _write_ledger_row(ledger, session, palace, 0, "SKIP: early error")
    _write_ledger_row(ledger, session, palace, 4, "2026-04-19T11:00:00Z")

    entry = read_ledger_entry(ledger, session, palace)
    assert entry is not None
    outcome, count, _ = entry
    assert outcome == "ok"
    assert count == 4


def test_read_ledger_entry_ignores_different_palace(tmp_path: Path) -> None:
    ledger = tmp_path / "mined.tsv"
    session = tmp_path / "s.md"
    _write_ledger_row(ledger, session, tmp_path / "OtherPalace", 5, "2026-04-19T10:00:00Z")

    entry = read_ledger_entry(ledger, session, tmp_path / "Mnemos-pilot")
    assert entry is None


# ---------------------------------------------------------------------------
# sessions_needing_run
# ---------------------------------------------------------------------------


def test_sessions_needing_run_filters_processed(tmp_path: Path) -> None:
    sdir = tmp_path / "Sessions"
    s1 = _make_session(sdir, "s1.md")
    s2 = _make_session(sdir, "s2.md")
    plan = build_plan(tmp_path)
    ledger = tmp_path / "mined.tsv"
    _write_ledger_row(ledger, s1, plan.skill_palace, 3, "2026-04-19T10:00:00Z")

    todo = sessions_needing_run(plan, ledger)
    assert s1 not in todo
    assert s2 in todo


def test_sessions_needing_run_retries_errors(tmp_path: Path) -> None:
    sdir = tmp_path / "Sessions"
    s1 = _make_session(sdir, "s1.md")
    plan = build_plan(tmp_path)
    ledger = tmp_path / "mined.tsv"
    # drawer_count=0 and no SKIP marker → error row
    _write_ledger_row(ledger, s1, plan.skill_palace, 0, "2026-04-19T10:00:00Z")

    todo = sessions_needing_run(plan, ledger)
    assert s1 in todo


def test_sessions_needing_run_honors_skip_marker(tmp_path: Path) -> None:
    """SKIP is an affirmative decision — don't retry."""
    sdir = tmp_path / "Sessions"
    s1 = _make_session(sdir, "s1.md")
    plan = build_plan(tmp_path)
    ledger = tmp_path / "mined.tsv"
    _write_ledger_row(ledger, s1, plan.skill_palace, 0, "SKIP: empty")

    todo = sessions_needing_run(plan, ledger)
    assert s1 not in todo


# ---------------------------------------------------------------------------
# run_pilot (runner mocking, no real claude subprocess)
# ---------------------------------------------------------------------------


def _make_fake_runner(
    *,
    ledger_path: Path,
    palace: Path,
    drawers_per_session: int = 3,
    usage_per_session: TokenUsage | None = None,
    exit_code: int = 0,
    outcome: str = "ok",
):
    """Builds a runner that mimics a successful skill call: writes a ledger row
    (as the real skill would) and returns synthetic JSON stdout.
    """
    usage_per_session = usage_per_session or TokenUsage(
        input_tokens=1000, output_tokens=300
    )

    def runner(cmd):
        # Extract session path from the /mnemos-mine-llm invocation. The
        # command shape is:
        #   ["claude", "--print", ..., "--output-format", "json",
        #    "/mnemos-mine-llm <session> <palace>"]
        slash_arg = cmd[-1]
        assert slash_arg.startswith("/mnemos-mine-llm ")
        session_str = slash_arg.split(" ", 2)[1]
        session = Path(session_str)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if outcome == "ok":
            _write_ledger_row(ledger_path, session, palace, drawers_per_session, now)
        elif outcome == "skip":
            _write_ledger_row(ledger_path, session, palace, 0, "SKIP: test")
        # outcome == "error" → no ledger row written, non-zero exit
        stdout = json.dumps({
            "type": "result",
            "result": f"{outcome.upper()} {session.name}",
            "usage": {
                "input_tokens": usage_per_session.input_tokens,
                "output_tokens": usage_per_session.output_tokens,
                "cache_read_input_tokens": usage_per_session.cache_read_input_tokens,
                "cache_creation_input_tokens": usage_per_session.cache_creation_input_tokens,
            },
        })
        return RunnerResult(exit_code=exit_code, stdout=stdout)

    return runner


def test_run_pilot_happy_path(tmp_path: Path) -> None:
    sdir = tmp_path / "Sessions"
    _make_session(sdir, "s1.md", mtime=time.time() - 100)
    _make_session(sdir, "s2.md", mtime=time.time() - 50)

    plan = build_plan(tmp_path, limit=2)
    ledger = tmp_path / "mined.tsv"
    runner = _make_fake_runner(ledger_path=ledger, palace=plan.skill_palace)

    result = run_pilot(plan, runner=runner, ledger_path=ledger)

    assert result.ok_count == 2
    assert result.skip_count == 0
    assert result.total_drawers == 6
    assert result.skill_total_tokens.input_tokens == 2000
    assert plan.skill_palace.exists()


def test_run_pilot_respects_ledger_resume(tmp_path: Path) -> None:
    sdir = tmp_path / "Sessions"
    s1 = _make_session(sdir, "s1.md", mtime=time.time() - 100)
    _make_session(sdir, "s2.md", mtime=time.time() - 50)

    plan = build_plan(tmp_path, limit=2)
    ledger = tmp_path / "mined.tsv"
    # Pre-populate: s1 already done against skill_palace
    _write_ledger_row(ledger, s1, plan.skill_palace, 7, "2026-04-19T09:00:00Z")

    call_log: list[str] = []

    def recording_runner(cmd):
        slash = cmd[-1]
        call_log.append(slash)
        session_str = slash.split(" ", 2)[1]
        session = Path(session_str)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _write_ledger_row(ledger, session, plan.skill_palace, 2, now)
        return RunnerResult(
            exit_code=0,
            stdout=json.dumps({"result": "OK", "usage": {"input_tokens": 500, "output_tokens": 100}}),
        )

    result = run_pilot(plan, runner=recording_runner, ledger_path=ledger)

    # s1 was pre-recorded (7 drawers), s2 runs fresh (2 drawers)
    assert len(call_log) == 1
    assert "s2.md" in call_log[0]
    assert result.total_drawers == 7 + 2
    assert result.ok_count == 2


def test_run_pilot_records_skip_outcomes(tmp_path: Path) -> None:
    sdir = tmp_path / "Sessions"
    _make_session(sdir, "s1.md", mtime=time.time() - 100)

    plan = build_plan(tmp_path, limit=1)
    ledger = tmp_path / "mined.tsv"
    runner = _make_fake_runner(ledger_path=ledger, palace=plan.skill_palace, outcome="skip")

    result = run_pilot(plan, runner=runner, ledger_path=ledger)

    assert result.ok_count == 0
    assert result.skip_count == 1
    assert result.outcomes[0].reason == "test"


def test_run_pilot_records_error_when_no_ledger_row(tmp_path: Path) -> None:
    sdir = tmp_path / "Sessions"
    _make_session(sdir, "s1.md", mtime=time.time() - 100)

    plan = build_plan(tmp_path, limit=1)
    ledger = tmp_path / "mined.tsv"

    def broken_runner(cmd):
        # No ledger row written → orchestrator must record this as error
        return RunnerResult(
            exit_code=0,
            stdout=json.dumps({"result": "", "usage": {}}),
        )

    result = run_pilot(plan, runner=broken_runner, ledger_path=ledger)

    assert result.error_count == 1
    assert "no ledger entry" in result.outcomes[0].reason


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------


def test_format_pilot_report_includes_required_sections(tmp_path: Path) -> None:
    sdir = tmp_path / "Sessions"
    _make_session(sdir, "s1.md", mtime=time.time() - 100)

    plan = build_plan(tmp_path, limit=1)
    ledger = tmp_path / "mined.tsv"
    runner = _make_fake_runner(ledger_path=ledger, palace=plan.skill_palace)
    result = run_pilot(plan, runner=runner, ledger_path=ledger)

    md = format_pilot_report(result)
    assert "# LLM-mine pilot" in md
    assert "## Quantitative summary" in md
    assert "## Qualitative judgment" in md
    assert "mnemos pilot --accept script" in md
    assert "mnemos pilot --accept skill" in md
    assert "Script-mine (`Mnemos/`)" in md
    assert "Skill-mine (`Mnemos-pilot/`)" in md


def test_format_pilot_report_counts_drawers_from_palace(tmp_path: Path) -> None:
    sdir = tmp_path / "Sessions"
    _make_session(sdir, "s1.md", mtime=time.time() - 100)
    plan = build_plan(tmp_path, limit=1)

    # Simulate that the skill-mine palace has 2 drawers in different halls
    skill_drawers_dir = plan.skill_palace / "wings" / "Mnemos" / "backend" / "decisions"
    skill_drawers_dir.mkdir(parents=True)
    (skill_drawers_dir / "2026-04-19-a.md").write_text("body", encoding="utf-8")
    (plan.skill_palace / "wings" / "Mnemos" / "backend" / "events").mkdir(parents=True)
    (plan.skill_palace / "wings" / "Mnemos" / "backend" / "events" / "2026-04-19-b.md").write_text("body", encoding="utf-8")
    # A leading-underscore file should NOT count (lazy _wing.md etc)
    (plan.skill_palace / "wings" / "Mnemos" / "_wing.md").write_text("summary", encoding="utf-8")

    result = PilotResult(plan=plan, outcomes=[])
    md = format_pilot_report(result)

    # Table row should reflect skill_count=2
    assert "| Total drawers | 0 | 2 |" in md
    assert "decisions:1" in md
    assert "events:1" in md


def test_write_pilot_report_creates_file_and_sets_path(tmp_path: Path) -> None:
    sdir = tmp_path / "Sessions"
    _make_session(sdir, "s1.md")
    plan = build_plan(tmp_path, limit=1)
    ledger = tmp_path / "mined.tsv"
    runner = _make_fake_runner(ledger_path=ledger, palace=plan.skill_palace)
    result = run_pilot(plan, runner=runner, ledger_path=ledger)

    path = write_pilot_report(result)

    assert path.exists()
    assert path.parent == tmp_path / "docs" / "pilots"
    assert result.report_path == path
    assert "# LLM-mine pilot" in path.read_text(encoding="utf-8")


def test_write_pilot_report_handles_filename_collision(tmp_path: Path) -> None:
    sdir = tmp_path / "Sessions"
    _make_session(sdir, "s1.md")
    plan = build_plan(tmp_path, limit=1)
    ledger = tmp_path / "mined.tsv"
    runner = _make_fake_runner(ledger_path=ledger, palace=plan.skill_palace)

    result1 = run_pilot(plan, runner=runner, ledger_path=ledger)
    path1 = write_pilot_report(result1)

    result2 = run_pilot(plan, runner=runner, ledger_path=ledger)
    path2 = write_pilot_report(result2)

    assert path1 != path2
    assert path2.name.endswith("-2.md")
