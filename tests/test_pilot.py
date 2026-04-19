"""Tests for mnemos.pilot — skill-mine pilot orchestrator."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mnemos.pilot import (
    AcceptResult,
    PilotError,
    PilotPlan,
    PilotResult,
    RunnerResult,
    SessionOutcome,
    TokenUsage,
    accept_script,
    accept_skill,
    build_plan,
    count_drawers_for_source,
    format_pilot_report,
    parse_claude_json_output,
    read_ledger_entry,
    run_pilot,
    source_breakdown,
    sources_needing_run,
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

    assert plan.source_count == 3
    assert plan.sources[0] == recent
    assert plan.sources[1] == middle


def test_build_plan_respects_limit(tmp_path: Path) -> None:
    sdir = tmp_path / "Sessions"
    for i in range(20):
        _make_session(sdir, f"2026-04-{i+1:02d}-s.md", mtime=time.time() - i)

    plan = build_plan(tmp_path, limit=5)
    assert plan.source_count == 5


def test_build_plan_raises_without_sessions_dir(tmp_path: Path) -> None:
    with pytest.raises(PilotError, match="No source files"):
        build_plan(tmp_path)


def test_build_plan_raises_with_empty_sessions_dir(tmp_path: Path) -> None:
    (tmp_path / "Sessions").mkdir()
    with pytest.raises(PilotError, match="No source files"):
        build_plan(tmp_path)


def test_build_plan_picks_from_all_source_dirs(tmp_path: Path) -> None:
    """4.2.12 — union of Sessions/, Topics/, and mining_sources entries."""
    session = _make_session(tmp_path / "Sessions", "s.md", mtime=time.time() - 10)
    topic = _make_session(tmp_path / "Topics", "t.md", mtime=time.time() - 20)
    # external mining_source entry (Claude Code-style memory dir)
    ext = tmp_path / "ext-memory"
    memfile = _make_session(ext, "feedback_x.md", mtime=time.time() - 30)

    (tmp_path / "mnemos.yaml").write_text(
        "mining_sources:\n"
        f"  - path: {ext}\n"
        "    mode: session\n"
        "    external: true\n",
        encoding="utf-8",
    )

    plan = build_plan(tmp_path, limit=10)
    assert set(plan.sources) == {session, topic, memfile}
    # Newest first: session (10s ago) > topic (20s) > memfile (30s)
    assert plan.sources == [session, topic, memfile]


def test_build_plan_skips_MEMORY_md(tmp_path: Path) -> None:
    """Type D MEMORY.md index files must not show up as sources."""
    sdir = tmp_path / "Sessions"
    session = _make_session(sdir, "real.md", mtime=time.time() - 10)
    # Create a MEMORY.md alongside — must be filtered
    memory_index = sdir / "MEMORY.md"
    memory_index.write_text(
        "# Memory index\n\n- [Foo](foo.md) — description\n", encoding="utf-8"
    )

    plan = build_plan(tmp_path, limit=10)
    assert plan.sources == [session]
    assert memory_index not in plan.sources


def test_build_plan_dedupes_overlapping_sources(tmp_path: Path) -> None:
    """mining_sources entry pointing at Sessions/ must not yield duplicates."""
    session = _make_session(tmp_path / "Sessions", "s.md")
    (tmp_path / "mnemos.yaml").write_text(
        "mining_sources:\n"
        f"  - path: {tmp_path / 'Sessions'}\n"
        "    mode: session\n",
        encoding="utf-8",
    )

    plan = build_plan(tmp_path, limit=10)
    assert plan.sources == [session]
    assert plan.source_count == 1


def test_build_plan_skips_leading_underscore_files(tmp_path: Path) -> None:
    """_wing.md / _room.md summaries must not be mined as input sources."""
    session = _make_session(tmp_path / "Sessions", "s.md")
    (tmp_path / "Sessions" / "_wing.md").write_text("noise", encoding="utf-8")

    plan = build_plan(tmp_path, limit=10)
    assert plan.sources == [session]


def test_build_plan_recurses_into_source_subdirs(tmp_path: Path) -> None:
    """memory/ dirs may nest files under subfolders — rglob must catch them."""
    ext = tmp_path / "ext-memory"
    nested = ext / "sub"
    deep = _make_session(nested, "deep.md")

    (tmp_path / "mnemos.yaml").write_text(
        f"mining_sources:\n  - path: {ext}\n    mode: session\n",
        encoding="utf-8",
    )

    plan = build_plan(tmp_path, limit=10)
    assert plan.sources == [deep]


def test_build_plan_raises_for_bad_vault(tmp_path: Path) -> None:
    missing = tmp_path / "nonexistent"
    with pytest.raises(PilotError, match="Vault path does not exist"):
        build_plan(missing)


def test_build_plan_rejects_negative_limit(tmp_path: Path) -> None:
    _make_session(tmp_path / "Sessions", "s.md")
    with pytest.raises(PilotError, match="limit must be >= 0"):
        build_plan(tmp_path, limit=-1)


def test_build_plan_limit_zero_picks_all_sources(tmp_path: Path) -> None:
    """4.2.13 — `--pilot-limit 0` means "mine everything" (full batch mode)."""
    sdir = tmp_path / "Sessions"
    for i in range(25):
        _make_session(sdir, f"s{i:02d}.md", mtime=time.time() - i)

    plan = build_plan(tmp_path, limit=0)
    assert plan.source_count == 25
    assert plan.limit == 0


def test_source_breakdown_groups_by_origin_dir(tmp_path: Path) -> None:
    """4.2.13 — CLI display helper buckets sources by Sessions/Topics/external."""
    s1 = _make_session(tmp_path / "Sessions", "a.md")
    s2 = _make_session(tmp_path / "Sessions", "b.md")
    t1 = _make_session(tmp_path / "Topics", "t.md")
    ext = tmp_path / "ext"
    m1 = _make_session(ext, "m.md")

    (tmp_path / "mnemos.yaml").write_text(
        f"mining_sources:\n  - path: {ext}\n    mode: session\n",
        encoding="utf-8",
    )

    breakdown = source_breakdown(tmp_path, [s1, s2, t1, m1])
    # Resolution order: Sessions, Topics, then yaml entries
    assert breakdown == [("Sessions", 2), ("Topics", 1), ("ext", 1)]


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
# sources_needing_run
# ---------------------------------------------------------------------------


def test_sources_needing_run_filters_processed(tmp_path: Path) -> None:
    sdir = tmp_path / "Sessions"
    s1 = _make_session(sdir, "s1.md")
    s2 = _make_session(sdir, "s2.md")
    plan = build_plan(tmp_path)
    ledger = tmp_path / "mined.tsv"
    _write_ledger_row(ledger, s1, plan.skill_palace, 3, "2026-04-19T10:00:00Z")

    todo = sources_needing_run(plan, ledger)
    assert s1 not in todo
    assert s2 in todo


def test_sources_needing_run_retries_errors(tmp_path: Path) -> None:
    sdir = tmp_path / "Sessions"
    s1 = _make_session(sdir, "s1.md")
    plan = build_plan(tmp_path)
    ledger = tmp_path / "mined.tsv"
    # drawer_count=0 and no SKIP marker → error row
    _write_ledger_row(ledger, s1, plan.skill_palace, 0, "2026-04-19T10:00:00Z")

    todo = sources_needing_run(plan, ledger)
    assert s1 in todo


def test_sources_needing_run_honors_skip_marker(tmp_path: Path) -> None:
    """SKIP is an affirmative decision — don't retry."""
    sdir = tmp_path / "Sessions"
    s1 = _make_session(sdir, "s1.md")
    plan = build_plan(tmp_path)
    ledger = tmp_path / "mined.tsv"
    _write_ledger_row(ledger, s1, plan.skill_palace, 0, "SKIP: empty")

    todo = sources_needing_run(plan, ledger)
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


def test_run_pilot_records_error_when_no_ledger_row_and_no_drawers(tmp_path: Path) -> None:
    """If neither ledger nor filesystem have evidence of the skill's work,
    the orchestrator correctly reports an error (Finding 2's real-error case).
    """
    sdir = tmp_path / "Sessions"
    _make_session(sdir, "s1.md", mtime=time.time() - 100)

    plan = build_plan(tmp_path, limit=1)
    ledger = tmp_path / "mined.tsv"

    def broken_runner(cmd):
        # No ledger row, no drawer files → real error
        return RunnerResult(
            exit_code=0,
            stdout=json.dumps({"result": "", "usage": {}}),
        )

    result = run_pilot(plan, runner=broken_runner, ledger_path=ledger)

    assert result.error_count == 1
    assert "no drawers" in result.outcomes[0].reason


def test_run_pilot_recovers_from_filesystem_when_ledger_missing(tmp_path: Path) -> None:
    """Finding 2 fix: skill wrote drawers but skipped ledger append →
    orchestrator recovers from filesystem, marks session OK.
    """
    sdir = tmp_path / "Sessions"
    session = _make_session(sdir, "long.md", mtime=time.time() - 100)
    plan = build_plan(tmp_path, limit=1)
    ledger = tmp_path / "mined.tsv"

    def drawer_writing_runner(cmd):
        # Simulate the real-world failure mode: runner writes 2 drawers but
        # forgets the ledger append step.
        slash = cmd[-1]
        _, sess_str, palace_str = slash.split(" ", 2)
        palace = Path(palace_str)
        _write_drawer(palace, "Mnemos", "r", "decisions", "d1.md", sess_str)
        _write_drawer(palace, "Mnemos", "r", "events", "d2.md", sess_str)
        return RunnerResult(
            exit_code=0,
            stdout=json.dumps({"result": "OK", "usage": {"input_tokens": 100, "output_tokens": 50}}),
        )

    result = run_pilot(plan, runner=drawer_writing_runner, ledger_path=ledger)

    assert result.ok_count == 1
    assert result.outcomes[0].drawer_count == 2
    assert "recovered from filesystem" in result.outcomes[0].reason


# ---------------------------------------------------------------------------
# Parallel execution (4.2.14)
# ---------------------------------------------------------------------------


def _make_slow_runner(
    ledger_path: Path,
    palace: Path,
    delay: float,
    *,
    active_counter: list[int] | None = None,
    peak_counter: list[int] | None = None,
    start_order: list[str] | None = None,
):
    """Runner that sleeps to simulate claude --print latency; records peak
    concurrency via shared counters (caller supplies zero-initialized lists).

    Note: the ledger write is serialized under a shared lock because this
    helper is called from multiple Python threads that share a single process.
    The real production skill runs in a separate ``claude --print`` subprocess
    where OS-level ``O_APPEND`` provides atomicity — we emulate that here to
    keep the concurrency assertions deterministic.
    """
    import threading
    lock = threading.Lock()

    def runner(cmd):
        slash = cmd[-1]
        session = Path(slash.split(" ", 2)[1])
        if active_counter is not None and peak_counter is not None:
            with lock:
                active_counter[0] += 1
                if active_counter[0] > peak_counter[0]:
                    peak_counter[0] = active_counter[0]
        if start_order is not None:
            with lock:
                start_order.append(session.name)
        time.sleep(delay)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with lock:
            _write_ledger_row(ledger_path, session, palace, 2, now)
        if active_counter is not None:
            with lock:
                active_counter[0] -= 1
        return RunnerResult(
            exit_code=0,
            stdout=json.dumps({
                "result": "OK", "usage": {"input_tokens": 100, "output_tokens": 50}
            }),
        )

    return runner


def test_run_pilot_parallel_caps_concurrency_at_max_workers(tmp_path: Path) -> None:
    """parallel=3 must never have more than 3 workers in flight."""
    sdir = tmp_path / "Sessions"
    for i in range(6):
        _make_session(sdir, f"s{i:02d}.md", mtime=time.time() - i)

    plan = build_plan(tmp_path, limit=6)
    ledger = tmp_path / "mined.tsv"
    active = [0]
    peak = [0]
    runner = _make_slow_runner(ledger, plan.skill_palace, delay=0.05,
                               active_counter=active, peak_counter=peak)

    result = run_pilot(plan, runner=runner, ledger_path=ledger, parallel=3)

    assert result.ok_count == 6
    assert peak[0] <= 3  # never more than 3 workers active
    assert peak[0] >= 2  # but at least some concurrency observed


def test_run_pilot_parallel_preserves_plan_order_in_outcomes(tmp_path: Path) -> None:
    """Futures complete out-of-order; final outcomes must reflect plan.sources order."""
    sdir = tmp_path / "Sessions"
    # 4 sources — mtime order: s03 newest, s00 oldest. build_plan returns
    # newest-first: [s03, s02, s01, s00].
    sources = [
        _make_session(sdir, f"s{i:02d}.md", mtime=time.time() - i * 10)
        for i in range(4)
    ]
    plan = build_plan(tmp_path, limit=4)
    expected_order = [p.name for p in plan.sources]
    ledger = tmp_path / "mined.tsv"

    # Variable delays so completion order diverges from submission order
    delays = {"s03.md": 0.15, "s02.md": 0.01, "s01.md": 0.10, "s00.md": 0.05}
    import threading
    write_lock = threading.Lock()

    def runner(cmd):
        slash = cmd[-1]
        session = Path(slash.split(" ", 2)[1])
        time.sleep(delays.get(session.name, 0.01))
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with write_lock:
            _write_ledger_row(ledger, session, plan.skill_palace, 1, now)
        return RunnerResult(
            exit_code=0,
            stdout=json.dumps({"result": "OK", "usage": {"input_tokens": 100}}),
        )

    result = run_pilot(plan, runner=runner, ledger_path=ledger, parallel=3)
    assert [o.session.name for o in result.outcomes] == expected_order


def test_run_pilot_sequential_when_parallel_1(tmp_path: Path) -> None:
    """parallel=1 (default) must keep strict submission-order execution."""
    sdir = tmp_path / "Sessions"
    _make_session(sdir, "s01.md", mtime=time.time() - 10)
    _make_session(sdir, "s02.md", mtime=time.time() - 20)

    plan = build_plan(tmp_path, limit=2)
    ledger = tmp_path / "mined.tsv"
    start_order: list[str] = []
    runner = _make_slow_runner(ledger, plan.skill_palace, delay=0.02,
                               start_order=start_order)

    run_pilot(plan, runner=runner, ledger_path=ledger, parallel=1)
    # Sequential = plan.sources order (newest first): s01 before s02
    assert start_order == ["s01.md", "s02.md"]


def test_run_pilot_progress_callback_fires_per_source(tmp_path: Path) -> None:
    """on_progress must be invoked once per completed source with running counts."""
    sdir = tmp_path / "Sessions"
    _make_session(sdir, "a.md", mtime=time.time() - 10)
    _make_session(sdir, "b.md", mtime=time.time() - 20)
    _make_session(sdir, "c.md", mtime=time.time() - 30)

    plan = build_plan(tmp_path, limit=3)
    ledger = tmp_path / "mined.tsv"
    runner = _make_fake_runner(
        ledger_path=ledger, palace=plan.skill_palace, drawers_per_session=5
    )

    events: list[dict] = []

    def on_progress(ev):
        events.append(ev)

    result = run_pilot(plan, runner=runner, ledger_path=ledger, on_progress=on_progress)

    assert len(events) == 3
    assert [e["index"] for e in events] == [1, 2, 3]
    assert all(e["total"] == 3 for e in events)
    assert events[-1]["ok_count"] == 3
    assert events[-1]["parallel"] == 1
    assert result.ok_count == 3

    # Per-source usage exposed; cumulative_tokens strictly monotonic
    for ev in events:
        assert ev["usage"].total() > 0
    cumulative = [e["cumulative_tokens"] for e in events]
    assert cumulative == sorted(cumulative)  # non-decreasing
    assert cumulative[-1] == sum(e["usage"].total() for e in events)


def test_run_pilot_progress_callback_skipped_for_resumed_entries(tmp_path: Path) -> None:
    """Resumed ledger rows shouldn't fire progress events — nothing ran."""
    sdir = tmp_path / "Sessions"
    s1 = _make_session(sdir, "already.md", mtime=time.time() - 10)
    _make_session(sdir, "fresh.md", mtime=time.time() - 20)

    plan = build_plan(tmp_path, limit=2)
    ledger = tmp_path / "mined.tsv"
    _write_ledger_row(ledger, s1, plan.skill_palace, 3, "2026-04-19T09:00:00Z")

    runner = _make_fake_runner(ledger_path=ledger, palace=plan.skill_palace)
    events: list[dict] = []
    run_pilot(plan, runner=runner, ledger_path=ledger, on_progress=events.append)

    # Only "fresh.md" actually ran; "already.md" was replayed silently.
    assert len(events) == 1
    assert events[0]["source"].name == "fresh.md"


def test_run_pilot_rejects_parallel_zero(tmp_path: Path) -> None:
    sdir = tmp_path / "Sessions"
    _make_session(sdir, "s.md")
    plan = build_plan(tmp_path, limit=1)
    with pytest.raises(PilotError, match="parallel must be >= 1"):
        run_pilot(plan, parallel=0)


def test_count_drawers_for_source_matches_normalized_paths(tmp_path: Path) -> None:
    palace = tmp_path / "P"
    session = tmp_path / "Sessions" / "s.md"
    session.parent.mkdir(parents=True)
    session.write_text("x", encoding="utf-8")
    other_session = tmp_path / "Sessions" / "other.md"
    other_session.write_text("y", encoding="utf-8")

    _write_drawer(palace, "Mnemos", "r", "decisions", "a.md", str(session))
    _write_drawer(palace, "Mnemos", "r", "events", "b.md", str(session))
    _write_drawer(palace, "Mnemos", "r", "decisions", "c.md", str(other_session))

    assert count_drawers_for_source(palace, session) == 2
    assert count_drawers_for_source(palace, other_session) == 1
    assert count_drawers_for_source(palace, tmp_path / "nope.md") == 0


def test_count_drawers_for_source_handles_missing_palace(tmp_path: Path) -> None:
    assert count_drawers_for_source(tmp_path / "nope", tmp_path / "s.md") == 0


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


def _write_drawer(
    palace: Path, wing: str, room: str, hall: str, name: str, source: str
) -> Path:
    d = palace / "wings" / wing / room / hall
    d.mkdir(parents=True, exist_ok=True)
    body = f"---\nwing: {wing}\nroom: {room}\nhall: {hall}\nsource: {source}\n---\n\n# body\n"
    p = d / name
    p.write_text(body, encoding="utf-8")
    return p


def test_format_pilot_report_counts_drawers_from_palace(tmp_path: Path) -> None:
    sdir = tmp_path / "Sessions"
    session = _make_session(sdir, "s1.md", mtime=time.time() - 100)
    plan = build_plan(tmp_path, limit=1)

    # Skill palace: 2 drawers in different halls, both sourced from s1
    _write_drawer(plan.skill_palace, "Mnemos", "backend", "decisions",
                  "2026-04-19-a.md", str(session))
    _write_drawer(plan.skill_palace, "Mnemos", "backend", "events",
                  "2026-04-19-b.md", str(session))
    # A leading-underscore file should NOT count (lazy _wing.md etc)
    (plan.skill_palace / "wings" / "Mnemos" / "_wing.md").write_text("summary", encoding="utf-8")

    result = PilotResult(plan=plan, outcomes=[])
    md = format_pilot_report(result)

    # Table row should reflect skill_count=2
    assert "| Total drawers | 0 | 2 |" in md
    assert "decisions:1" in md
    assert "events:1" in md


def test_format_pilot_report_filters_non_pilot_drawers(tmp_path: Path) -> None:
    """Finding 3 fix: Total drawers counts only drawers sourced from pilot
    sessions, not the whole palace.
    """
    import os
    sdir = tmp_path / "Sessions"
    pilot_session = _make_session(sdir, "pilot.md", mtime=time.time() - 10)
    other_session = sdir / "other.md"
    other_session.write_text("other\n", encoding="utf-8")
    # other_session must be OLDER so limit=1 picks pilot_session
    os.utime(other_session, (time.time() - 1000, time.time() - 1000))

    plan = build_plan(tmp_path, limit=1)
    assert plan.sources == [pilot_session]

    # Script palace has 2 drawers total: 1 from pilot session + 1 from other
    _write_drawer(plan.script_palace, "Mnemos", "r", "decisions",
                  "from-pilot.md", str(pilot_session))
    _write_drawer(plan.script_palace, "Mnemos", "r", "events",
                  "from-other.md", str(other_session))

    # Skill palace: 1 drawer from pilot session
    _write_drawer(plan.skill_palace, "Mnemos", "r", "decisions",
                  "skill-pilot.md", str(pilot_session))

    result = PilotResult(plan=plan, outcomes=[])
    md = format_pilot_report(result)

    # Script-mine side now shows ONLY pilot-session drawer (1), not 2
    assert "| Total drawers | 1 | 1 |" in md
    # Hall distribution follows same filter — no events: from other session
    # should appear
    assert "events" not in md.split("Hall distribution")[1].split("|")[2]


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


# ---------------------------------------------------------------------------
# Accept — pilot promotion
# ---------------------------------------------------------------------------


def _make_palace(vault: Path, name: str, drawer_marker: str = "x") -> Path:
    """Create a minimal palace root with a single drawer file for verification."""
    palace = vault / name
    drawer_dir = palace / "wings" / "Mnemos" / "backend" / "decisions"
    drawer_dir.mkdir(parents=True)
    (drawer_dir / f"drawer-{drawer_marker}.md").write_text(
        f"marker={drawer_marker}", encoding="utf-8"
    )
    return palace


def _write_yaml(vault: Path, contents: str) -> Path:
    p = vault / "mnemos.yaml"
    p.write_text(contents, encoding="utf-8")
    return p


def test_accept_script_recycles_pilot_palace(tmp_path: Path) -> None:
    _make_palace(tmp_path, "Mnemos", drawer_marker="script")
    _make_palace(tmp_path, "Mnemos-pilot", drawer_marker="skill")

    result = accept_script(tmp_path)

    assert result.mode == "script"
    assert len(result.recycled_paths) == 1
    assert not (tmp_path / "Mnemos-pilot").exists()
    # Mnemos/ untouched
    assert (tmp_path / "Mnemos").exists()
    assert (tmp_path / "Mnemos" / "wings" / "Mnemos" / "backend" / "decisions"
            / "drawer-script.md").read_text(encoding="utf-8") == "marker=script"
    # Recycled content preserved
    recycled = result.recycled_paths[0]
    assert recycled.parent == tmp_path / "_recycled"
    assert (recycled / "wings" / "Mnemos" / "backend" / "decisions"
            / "drawer-skill.md").read_text(encoding="utf-8") == "marker=skill"


def test_accept_script_tolerates_missing_pilot_palace(tmp_path: Path) -> None:
    _make_palace(tmp_path, "Mnemos")
    result = accept_script(tmp_path)
    assert result.recycled_paths == []


def test_accept_skill_promotes_and_recycles(tmp_path: Path) -> None:
    _make_palace(tmp_path, "Mnemos", drawer_marker="script")
    _make_palace(tmp_path, "Mnemos-pilot", drawer_marker="skill")
    _write_yaml(tmp_path,
        "vault_path: " + str(tmp_path).replace("\\", "/") + "\n"
        "languages: [tr, en]\n"
        "use_llm: false\n"
    )

    result = accept_skill(tmp_path, reindex=False)

    assert result.mode == "skill"
    # Old script palace in _recycled
    assert len(result.recycled_paths) == 1
    recycled = result.recycled_paths[0]
    assert (recycled / "wings" / "Mnemos" / "backend" / "decisions"
            / "drawer-script.md").exists()
    # Pilot palace promoted to Mnemos/
    assert not (tmp_path / "Mnemos-pilot").exists()
    assert (tmp_path / "Mnemos" / "wings" / "Mnemos" / "backend" / "decisions"
            / "drawer-skill.md").read_text(encoding="utf-8") == "marker=skill"
    # yaml now has mine_mode: skill
    assert result.yaml_updated is True
    yaml_text = (tmp_path / "mnemos.yaml").read_text(encoding="utf-8")
    assert "mine_mode: skill" in yaml_text
    assert "languages: [tr, en]" in yaml_text  # other keys preserved
    # reindex=False → advisory warning pointing to --from-palace
    assert result.index_stale_warning
    assert "--from-palace" in result.index_stale_warning
    assert result.indexed_drawers == 0


def test_accept_skill_raises_without_pilot_palace(tmp_path: Path) -> None:
    _make_palace(tmp_path, "Mnemos")
    with pytest.raises(PilotError, match="Skill palace not found"):
        accept_skill(tmp_path)


def test_accept_skill_tolerates_missing_script_palace(tmp_path: Path) -> None:
    """Fresh vault: no Mnemos/, just Mnemos-pilot/ — still promote cleanly."""
    _make_palace(tmp_path, "Mnemos-pilot", drawer_marker="skill")
    _write_yaml(tmp_path, "vault_path: /tmp\n")

    result = accept_skill(tmp_path, reindex=False)

    assert result.recycled_paths == []
    assert (tmp_path / "Mnemos" / "wings" / "Mnemos" / "backend" / "decisions"
            / "drawer-skill.md").exists()


def test_accept_skill_updates_existing_mine_mode_key(tmp_path: Path) -> None:
    _make_palace(tmp_path, "Mnemos-pilot")
    _write_yaml(tmp_path,
        "vault_path: /tmp\n"
        "mine_mode: script\n"
        "use_llm: false\n"
    )

    accept_skill(tmp_path)

    yaml_text = (tmp_path / "mnemos.yaml").read_text(encoding="utf-8")
    assert "mine_mode: skill" in yaml_text
    assert "mine_mode: script" not in yaml_text
    assert "use_llm: false" in yaml_text


def test_accept_skill_triggers_reindex_by_default(tmp_path: Path, monkeypatch) -> None:
    """4.2.9: accept_skill(reindex=True) should call _reindex_after_accept."""
    _make_palace(tmp_path, "Mnemos-pilot", drawer_marker="skill")
    _write_yaml(tmp_path, "vault_path: /tmp\n")

    calls: list[tuple[Path, Path]] = []

    def fake_reindex(vault, palace):
        calls.append((Path(vault), Path(palace)))
        return 7

    monkeypatch.setattr("mnemos.pilot._reindex_after_accept", fake_reindex)

    result = accept_skill(tmp_path)  # reindex=True by default

    assert len(calls) == 1
    assert calls[0][0] == tmp_path
    assert calls[0][1] == tmp_path / "Mnemos"  # the promoted palace
    assert result.indexed_drawers == 7
    assert result.index_stale_warning == ""  # no warning on success


def test_accept_skill_surfaces_reindex_failure(tmp_path: Path, monkeypatch) -> None:
    _make_palace(tmp_path, "Mnemos-pilot")
    _write_yaml(tmp_path, "vault_path: /tmp\n")

    def broken_reindex(vault, palace):
        raise RuntimeError("backend unavailable")

    monkeypatch.setattr("mnemos.pilot._reindex_after_accept", broken_reindex)

    result = accept_skill(tmp_path)

    # File moves still succeeded
    assert (tmp_path / "Mnemos").exists()
    assert result.indexed_drawers == 0
    assert "Index rebuild failed" in result.index_stale_warning
    assert "backend unavailable" in result.index_stale_warning


def test_accept_script_collision_safe(tmp_path: Path) -> None:
    """Two accepts in the same day should not overwrite each other's recycled dir."""
    # First accept
    _make_palace(tmp_path, "Mnemos-pilot", drawer_marker="first")
    r1 = accept_script(tmp_path)
    assert len(r1.recycled_paths) == 1

    # Second accept same day (different pilot content)
    _make_palace(tmp_path, "Mnemos-pilot", drawer_marker="second")
    r2 = accept_script(tmp_path)

    assert r1.recycled_paths[0] != r2.recycled_paths[0]
    # Both recycled dirs still have their respective content
    assert (r1.recycled_paths[0] / "wings" / "Mnemos" / "backend" / "decisions"
            / "drawer-first.md").exists()
    assert (r2.recycled_paths[0] / "wings" / "Mnemos" / "backend" / "decisions"
            / "drawer-second.md").exists()
