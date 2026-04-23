"""Tests for mnemos.recall_briefing — cwd-aware SessionStart briefing hook."""
from __future__ import annotations

import json
from pathlib import Path

# Minimum-viable JSONL content: 3 real user turns (meets MIN_USER_TURNS=3
# threshold used by find_unrefined_jsonls_for_cwd). Use this in tests whose
# stub JSONLs must survive the min-turns filter; write raw "{}" if you
# explicitly want the JSONL to be filtered out as fork-bomb-style noise.
_REAL_JSONL_3_TURNS = (
    '{"type":"user","message":{"role":"user","content":"msg1"}}\n'
    '{"type":"assistant","message":{}}\n'
    '{"type":"user","message":{"role":"user","content":"msg2"}}\n'
    '{"type":"assistant","message":{}}\n'
    '{"type":"user","message":{"role":"user","content":"msg3"}}\n'
)

from mnemos.recall_briefing import (
    cwd_to_slug,
    load_state,
    save_state,
    STATE_FILENAME,
    CwdState,
)


# --- slug tests ---

def test_slug_simple_windows_path() -> None:
    assert cwd_to_slug("C:\\Projects\\farcry") == "C--Projects-farcry"


def test_slug_preserves_underscores() -> None:
    # my-app vs my_app should NOT collide
    a = cwd_to_slug("C:\\Projects\\my-app")
    b = cwd_to_slug("C:\\Projects\\my_app")
    assert a != b
    assert a == "C--Projects-my-app"
    assert b == "C--Projects-my_app"


def test_slug_trailing_slash_normalized() -> None:
    assert cwd_to_slug("C:\\Projects\\farcry\\") == cwd_to_slug("C:\\Projects\\farcry")


def test_slug_trailing_whitespace_normalized() -> None:
    assert cwd_to_slug("  C:\\Projects\\farcry  ") == cwd_to_slug("C:\\Projects\\farcry")


def test_slug_double_dash_collapsed() -> None:
    # "C:\\" produces "C--"; multiple consecutive special chars collapse
    result = cwd_to_slug("C:\\\\\\foo")
    # No triple or more dashes in output
    assert "---" not in result


def test_slug_non_ascii_maps_to_dash_matching_claude_code() -> None:
    """Non-ASCII chars (Turkish ü/ğ, German ä, Japanese etc.) must be replaced
    with '-' to match Claude Code's actual ~/.claude/projects/<slug>/ algorithm.

    Previously used Unicode \\w which preserved these letters, producing
    slugs that never matched Claude Code's project dirs — breaking SUB-B2's
    unrefined-JSONL discovery for any cwd with non-ASCII chars (e.g. the
    Turkish "Masaüstü" Desktop folder).
    """
    # Real Claude Code slug for C:\Users\tugrademirors\OneDrive\Masaüstü\farcry
    # observed in ledger: C--Users-tugrademirors-OneDrive-Masa-st--farcry
    assert cwd_to_slug("C:\\Users\\u\\OneDrive\\Masaüstü\\farcry") == \
        "C--Users-u-OneDrive-Masa-st--farcry"


def test_slug_ascii_only_unchanged_after_non_ascii_fix() -> None:
    """ASCII-only cwds must not regress when non-ASCII handling changes."""
    assert cwd_to_slug("C:\\Projeler\\mnemos") == "C--Projeler-mnemos"
    assert cwd_to_slug("/home/user/my-project") == "-home-user-my-project"


def test_slug_various_non_ascii_scripts_all_become_dash() -> None:
    """Cross-script coverage: German, Japanese, Chinese, emoji all map to '-'."""
    assert cwd_to_slug("C:\\Müller") == "C--M-ller"
    assert cwd_to_slug("C:\\café") == "C--caf-"
    # Multi-byte chars each → one dash, consecutive dashes collapse to --
    assert "---" not in cwd_to_slug("C:\\日本語")


# --- state tests ---

def test_load_state_missing_returns_empty(tmp_path: Path) -> None:
    state = load_state(tmp_path)
    assert state.cwds == {}
    assert state.version == 1


def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    state = CwdState()
    state.cwds["slug1"] = {
        "cwd": "C:\\x",
        "first_seen": 100.0,
        "last_seen": 200.0,
        "visit_count": 3,
    }
    save_state(tmp_path, state)

    loaded = load_state(tmp_path)
    assert loaded.cwds["slug1"]["visit_count"] == 3
    assert loaded.cwds["slug1"]["cwd"] == "C:\\x"


def test_load_state_corrupt_json_resets(tmp_path: Path) -> None:
    (tmp_path / STATE_FILENAME).write_text("not json", encoding="utf-8")
    state = load_state(tmp_path)
    assert state.cwds == {}


def test_save_state_writes_atomic(tmp_path: Path) -> None:
    state = CwdState()
    state.cwds["a"] = {"visit_count": 1}
    save_state(tmp_path, state)
    tmp_file = tmp_path / (STATE_FILENAME + ".tmp")
    assert not tmp_file.exists()
    assert (tmp_path / STATE_FILENAME).exists()


# --- helper tests ---

from mnemos.recall_briefing import (
    read_recall_mode,
    cache_path_for,
    read_cache_body,
    write_cache,
    count_refined_sessions_for_cwd,
)


def test_read_recall_mode_default_script(tmp_path: Path) -> None:
    assert read_recall_mode(tmp_path) == "script"


def test_read_recall_mode_skill(tmp_path: Path) -> None:
    (tmp_path / "mnemos.yaml").write_text(
        "palace_root: Mnemos\nrecall_mode: skill\n",
        encoding="utf-8",
    )
    assert read_recall_mode(tmp_path) == "skill"


def test_cache_path_for_returns_cache_dir(tmp_path: Path) -> None:
    p = cache_path_for(tmp_path, "C--Projects-farcry")
    assert p.parent.name == ".mnemos-briefings"
    assert p.name == "C--Projects-farcry.md"


def test_read_cache_body_strips_frontmatter(tmp_path: Path) -> None:
    cache = tmp_path / ".mnemos-briefings" / "slug.md"
    cache.parent.mkdir()
    cache.write_text(
        "---\ncwd: C:\\x\ngenerated_at: 2026-04-23\nsession_count_used: 3\n---\n"
        "\n**Aktif durum:** Body content here.\n",
        encoding="utf-8",
    )
    body = read_cache_body(cache)
    assert "**Aktif durum:**" in body
    assert "session_count_used" not in body


def test_write_cache_round_trip(tmp_path: Path) -> None:
    cache = tmp_path / ".mnemos-briefings" / "slug.md"
    write_cache(
        cache,
        body="**Aktif durum:** x\n",
        cwd="C:\\Projects\\farcry",
        session_count=5,
        drawer_count=12,
    )
    assert cache.exists()
    text = cache.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "cwd: C:\\Projects\\farcry" in text
    assert "session_count_used: 5" in text
    assert "**Aktif durum:**" in text


def test_count_refined_sessions_for_cwd(tmp_path: Path) -> None:
    sessions = tmp_path / "Sessions"
    sessions.mkdir()
    (sessions / "2026-04-01-a.md").write_text(
        "---\ndate: 2026-04-01\ncwd: C:\\Projects\\farcry\n---\nbody\n",
        encoding="utf-8",
    )
    (sessions / "2026-04-02-b.md").write_text(
        "---\ndate: 2026-04-02\ncwd: C:\\Projects\\farcry\n---\nbody\n",
        encoding="utf-8",
    )
    (sessions / "2026-04-03-c.md").write_text(
        "---\ndate: 2026-04-03\ncwd: C:\\Other\n---\nbody\n",
        encoding="utf-8",
    )
    # Session without cwd frontmatter — excluded
    (sessions / "2026-04-04-d.md").write_text(
        "---\ndate: 2026-04-04\n---\nbody\n",
        encoding="utf-8",
    )

    count = count_refined_sessions_for_cwd(tmp_path, "C:\\Projects\\farcry")
    assert count == 2


# --- unrefined JSONL discovery tests ---

from mnemos.recall_briefing import (
    find_unrefined_jsonls_for_cwd,
    load_refine_ledger_jsonls,
)


def test_load_refine_ledger_jsonls_extracts_ok_jsonl_paths(tmp_path: Path) -> None:
    ledger = tmp_path / "processed.tsv"
    # Real ledger format: <jsonl>\tOK\t<session_md> (3 cols, no timestamp)
    ledger.write_text(
        "C:\\proj\\a.jsonl\tOK\t2026-04-01.md\n"
        "C:\\proj\\b.jsonl\tSKIP\tnone\n"
        "C:\\proj\\c.jsonl\tOK\t2026-04-02.md\n",
        encoding="utf-8",
    )
    jsonls = load_refine_ledger_jsonls(ledger)
    assert "C:\\proj\\a.jsonl" in jsonls
    assert "C:\\proj\\c.jsonl" in jsonls
    assert "C:\\proj\\b.jsonl" not in jsonls  # SKIP excluded


def test_find_unrefined_jsonls_for_cwd_returns_unprocessed(tmp_path: Path) -> None:
    proj_root = tmp_path / ".claude" / "projects" / "C--Projects-farcry"
    proj_root.mkdir(parents=True)
    jsonl_old = proj_root / "uuid-old.jsonl"
    jsonl_new = proj_root / "uuid-new.jsonl"
    jsonl_old.write_text(_REAL_JSONL_3_TURNS, encoding="utf-8")
    jsonl_new.write_text(_REAL_JSONL_3_TURNS, encoding="utf-8")

    ledger = tmp_path / "processed.tsv"
    ledger.write_text(
        f"{jsonl_old}\tOK\t2026-04-01.md\n",
        encoding="utf-8",
    )

    result = find_unrefined_jsonls_for_cwd(
        cwd_slug="C--Projects-farcry",
        projects_root=tmp_path / ".claude" / "projects",
        ledger=ledger,
    )
    assert jsonl_new in result
    assert jsonl_old not in result


def test_find_unrefined_jsonls_skips_short_transcripts(tmp_path: Path) -> None:
    """JSONLs with fewer than MIN_USER_TURNS real user turns are noise —
    fork-bomb byproducts, '/clear' resume sessions, aborted sessions.
    Without this filter, SUB-B2 spent ~4 minutes sync-refining 3 fork-bomb
    JSONLs (no real content) on every session start, wasting latency for
    zero briefing value. Matches auto_refine's picker behavior (v0.3.11
    MIN_USER_TURNS filter).
    """
    proj_root = tmp_path / ".claude" / "projects" / "C--test"
    proj_root.mkdir(parents=True)

    # 1-turn fork-bomb trash (no tool_result; 1 real user turn)
    short = proj_root / "short.jsonl"
    short.write_text(
        '{"type":"user","message":{"role":"user","content":"hi"}}\n',
        encoding="utf-8",
    )

    # Real 3-turn session
    real = proj_root / "real.jsonl"
    real.write_text(
        '{"type":"user","message":{"role":"user","content":"msg1"}}\n'
        '{"type":"assistant","message":{}}\n'
        '{"type":"user","message":{"role":"user","content":"msg2"}}\n'
        '{"type":"assistant","message":{}}\n'
        '{"type":"user","message":{"role":"user","content":"msg3"}}\n',
        encoding="utf-8",
    )

    ledger = tmp_path / "processed.tsv"
    ledger.write_text("", encoding="utf-8")

    result = find_unrefined_jsonls_for_cwd(
        cwd_slug="C--test",
        projects_root=tmp_path / ".claude" / "projects",
        ledger=ledger,
    )
    assert real in result, "Real multi-turn JSONL must be kept in pending"
    assert short not in result, "1-turn fork-bomb trash must be filtered out"


def test_find_unrefined_jsonls_tool_result_turns_dont_count(tmp_path: Path) -> None:
    """Claude Code stores tool_result messages as type=user. Those must NOT
    count toward user-turn threshold — a 1-user-turn session with 5 tool
    calls is still 1-turn noise for the miner."""
    proj_root = tmp_path / ".claude" / "projects" / "C--test2"
    proj_root.mkdir(parents=True)

    # 1 real user turn + 5 tool_result "user" messages — still 1 effective turn
    tool_heavy = proj_root / "tool_heavy.jsonl"
    tool_heavy.write_text(
        '{"type":"user","message":{"role":"user","content":"do stuff"}}\n'
        + ('{"type":"user","message":{"role":"user","content":[{"type":"tool_result","content":"x"}]}}\n' * 5),
        encoding="utf-8",
    )

    ledger = tmp_path / "processed.tsv"
    ledger.write_text("", encoding="utf-8")

    result = find_unrefined_jsonls_for_cwd(
        cwd_slug="C--test2",
        projects_root=tmp_path / ".claude" / "projects",
        ledger=ledger,
    )
    assert tool_heavy not in result


def test_find_unrefined_jsonls_missing_project_dir_returns_empty(tmp_path: Path) -> None:
    ledger = tmp_path / "processed.tsv"
    ledger.write_text("", encoding="utf-8")
    result = find_unrefined_jsonls_for_cwd(
        cwd_slug="C--nowhere",
        projects_root=tmp_path,
        ledger=ledger,
    )
    assert result == []


# --- status writes ---

from mnemos.recall_briefing import (
    STATUS_FILENAME,
    write_status,
    read_status,
)


def test_write_status_creates_file(tmp_path: Path) -> None:
    write_status(tmp_path, phase="refining", current=1, total=2, cwd_slug="s")
    p = tmp_path / STATUS_FILENAME
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["phase"] == "refining"
    assert data["current"] == 1
    assert data["total"] == 2
    assert data["cwd_slug"] == "s"
    assert data["sub_phase"] == "catch-up"  # default when phase != idle


def test_write_status_idle_phase(tmp_path: Path) -> None:
    write_status(tmp_path, phase="idle", last_outcome="ok")
    data = json.loads((tmp_path / STATUS_FILENAME).read_text(encoding="utf-8"))
    assert data["phase"] == "idle"
    assert data["last_outcome"] == "ok"


def test_write_status_preserves_existing_fields(tmp_path: Path) -> None:
    # Auto-refine hook may have written fields like last_ok
    initial = {"phase": "idle", "last_ok": 5, "backlog": 10}
    (tmp_path / STATUS_FILENAME).write_text(json.dumps(initial), encoding="utf-8")
    write_status(tmp_path, phase="briefing", cwd_slug="s")
    data = read_status(tmp_path)
    assert data["phase"] == "briefing"
    assert data["last_ok"] == 5  # preserved
    assert data["backlog"] == 10  # preserved


def test_read_status_missing_returns_empty(tmp_path: Path) -> None:
    assert read_status(tmp_path) == {}


# --- subprocess runner tests ---

from mnemos.recall_briefing import (
    run_refine_sync,
    run_mine_sync,
    run_brief_sync,
    RefineResult,
    MineResult,
    BriefResult,
)


def test_run_refine_sync_invokes_claude_with_skill(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_runner(cmd):
        calls.append(list(cmd))
        return 0

    jsonl = tmp_path / "x.jsonl"
    jsonl.write_text("{}\n", encoding="utf-8")
    result = run_refine_sync(jsonl, runner=fake_runner)
    assert result.ok is True
    assert len(calls) == 1
    cmd = calls[0]
    assert cmd[0] == "claude"
    assert "--print" in cmd
    assert "--dangerously-skip-permissions" in cmd
    assert any(str(jsonl) in arg for arg in cmd)
    assert any("mnemos-refine-transcripts" in arg for arg in cmd)


def test_run_refine_sync_nonzero_exit_fails(tmp_path: Path) -> None:
    jsonl = tmp_path / "x.jsonl"
    jsonl.write_text("{}\n", encoding="utf-8")
    result = run_refine_sync(jsonl, runner=lambda cmd: 2)
    assert result.ok is False


def test_run_mine_sync_invokes_claude_with_session_md(tmp_path: Path) -> None:
    session_md = tmp_path / "2026-04-01-foo.md"
    session_md.write_text("---\n---\nbody\n", encoding="utf-8")
    captured: list[list[str]] = []
    result = run_mine_sync(session_md, runner=lambda cmd: captured.append(list(cmd)) or 0)
    assert result.ok is True
    assert any("mnemos-mine-llm" in a for a in captured[0])


def test_run_brief_sync_captures_stdout(tmp_path: Path) -> None:
    def fake_runner_with_output(cmd, stdout_path=None):
        if stdout_path is not None:
            Path(stdout_path).write_text("**Aktif durum:** test briefing body.\n", encoding="utf-8")
        return 0

    result = run_brief_sync(
        cwd="C:\\Projects\\farcry",
        runner=fake_runner_with_output,
    )
    assert result.ok is True
    assert "**Aktif durum:**" in result.body


# --- handle_session_start: decision tree ---

from mnemos.recall_briefing import (
    handle_session_start,
    SessionStartInput,
    HandleOutcome,
)


def test_first_visit_records_state_no_injection(tmp_path: Path) -> None:
    (tmp_path / "mnemos.yaml").write_text("recall_mode: skill\n", encoding="utf-8")

    inp = SessionStartInput(
        cwd="C:\\Projects\\farcry",
        source="startup",
        transcript_path="/c/Users/x/.claude/projects/C--Projects-farcry/uuid.jsonl",
    )

    result = handle_session_start(
        inp,
        vault=tmp_path,
        projects_root=tmp_path / "_no_projects",  # intentionally nonexistent
        ledger=tmp_path / "_no_ledger.tsv",
        subprocess_runner=lambda cmd: 0,
        brief_runner=lambda cmd, stdout_path=None: 0,
    )
    assert result.outcome == "first_visit"
    assert result.injected_context == ""

    state = load_state(tmp_path)
    slug = cwd_to_slug("C:\\Projects\\farcry")
    assert slug in state.cwds
    assert state.cwds[slug]["visit_count"] == 1


def test_return_visit_no_pending_no_cache_bg_regen(tmp_path: Path) -> None:
    (tmp_path / "mnemos.yaml").write_text("recall_mode: skill\n", encoding="utf-8")
    (tmp_path / "Sessions").mkdir()
    slug = cwd_to_slug("C:\\Projects\\farcry")
    state = CwdState()
    state.cwds[slug] = {"cwd": "C:\\Projects\\farcry", "first_seen": 0.0, "last_seen": 0.0, "visit_count": 1}
    save_state(tmp_path, state)

    inp = SessionStartInput(cwd="C:\\Projects\\farcry", source="startup", transcript_path="x")

    result = handle_session_start(
        inp,
        vault=tmp_path,
        projects_root=tmp_path / "projects_empty",
        ledger=tmp_path / "_no_ledger.tsv",
        subprocess_runner=lambda cmd: 0,
        brief_runner=lambda cmd, stdout_path=None: 0,
    )
    assert result.outcome == "fast_path_no_cache"
    assert result.injected_context == ""


def test_return_visit_cache_fresh_injects_and_bg_regen(tmp_path: Path) -> None:
    (tmp_path / "mnemos.yaml").write_text("recall_mode: skill\n", encoding="utf-8")
    (tmp_path / "Sessions").mkdir()
    slug = cwd_to_slug("C:\\Projects\\farcry")
    state = CwdState()
    state.cwds[slug] = {"cwd": "C:\\Projects\\farcry", "first_seen": 0.0, "last_seen": 0.0, "visit_count": 1}
    save_state(tmp_path, state)

    (tmp_path / "Sessions" / "a.md").write_text(
        "---\ncwd: C:\\Projects\\farcry\n---\nbody\n", encoding="utf-8"
    )
    (tmp_path / "Sessions" / "b.md").write_text(
        "---\ncwd: C:\\Projects\\farcry\n---\nbody\n", encoding="utf-8"
    )
    cache_p = cache_path_for(tmp_path, slug)
    write_cache(cache_p, body="**Aktif durum:** x\n", cwd="C:\\Projects\\farcry", session_count=2, drawer_count=0)

    inp = SessionStartInput(cwd="C:\\Projects\\farcry", source="startup", transcript_path="x")

    result = handle_session_start(
        inp,
        vault=tmp_path,
        projects_root=tmp_path / "projects_empty",
        ledger=tmp_path / "_no_ledger.tsv",
        subprocess_runner=lambda cmd: 0,
        brief_runner=lambda cmd, stdout_path=None: 0,
    )
    assert result.outcome == "fast_path_injected"
    assert "**Aktif durum:**" in result.injected_context


def test_return_visit_cache_stale_triggers_sync_regen(tmp_path: Path) -> None:
    (tmp_path / "mnemos.yaml").write_text("recall_mode: skill\n", encoding="utf-8")
    (tmp_path / "Sessions").mkdir()
    slug = cwd_to_slug("C:\\Projects\\farcry")
    state = CwdState()
    state.cwds[slug] = {"cwd": "C:\\Projects\\farcry", "first_seen": 0.0, "last_seen": 0.0, "visit_count": 1}
    save_state(tmp_path, state)

    for i in range(5):
        (tmp_path / "Sessions" / f"s{i}.md").write_text(
            "---\ncwd: C:\\Projects\\farcry\n---\nbody\n", encoding="utf-8"
        )
    cache_p = cache_path_for(tmp_path, slug)
    write_cache(cache_p, body="old briefing\n", cwd="C:\\Projects\\farcry", session_count=1, drawer_count=0)

    def fake_brief(cmd, stdout_path=None):
        if stdout_path is not None:
            Path(stdout_path).write_text("**Aktif durum:** fresh briefing\n", encoding="utf-8")
        return 0

    inp = SessionStartInput(cwd="C:\\Projects\\farcry", source="startup", transcript_path="x")
    result = handle_session_start(
        inp,
        vault=tmp_path,
        projects_root=tmp_path / "projects_empty",
        ledger=tmp_path / "_no_ledger.tsv",
        subprocess_runner=lambda cmd: 0,
        brief_runner=fake_brief,
    )
    assert result.outcome == "sync_regen_injected"
    assert "fresh briefing" in result.injected_context


def test_compact_source_exits_silently(tmp_path: Path) -> None:
    (tmp_path / "mnemos.yaml").write_text("recall_mode: skill\n", encoding="utf-8")
    inp = SessionStartInput(cwd="C:\\x", source="compact", transcript_path="y")
    result = handle_session_start(
        inp,
        vault=tmp_path,
        projects_root=tmp_path,
        ledger=tmp_path / "_nl",
        subprocess_runner=lambda cmd: 0,
        brief_runner=lambda cmd, stdout_path=None: 0,
    )
    assert result.outcome == "skipped_source"


def test_recall_mode_not_skill_exits(tmp_path: Path) -> None:
    # No mnemos.yaml → default script
    inp = SessionStartInput(cwd="C:\\x", source="startup", transcript_path="y")
    result = handle_session_start(
        inp,
        vault=tmp_path,
        projects_root=tmp_path,
        ledger=tmp_path / "_nl",
        subprocess_runner=lambda cmd: 0,
        brief_runner=lambda cmd, stdout_path=None: 0,
    )
    assert result.outcome == "skipped_mode"


# --- SUB-B2 blocking catch-up ---

def test_sub_b2_refines_and_mines_each_pending(tmp_path: Path) -> None:
    """Pending JSONL → refine → read session_md from ledger → mine → brief."""
    (tmp_path / "mnemos.yaml").write_text("recall_mode: skill\n", encoding="utf-8")
    sessions = tmp_path / "Sessions"
    sessions.mkdir()

    slug = cwd_to_slug("C:\\Projects\\farcry")
    state = CwdState()
    state.cwds[slug] = {"cwd": "C:\\Projects\\farcry", "first_seen": 0.0, "last_seen": 0.0, "visit_count": 1}
    save_state(tmp_path, state)

    proj_root = tmp_path / ".claude" / "projects" / slug
    proj_root.mkdir(parents=True)
    pending_jsonl = proj_root / "pending-uuid.jsonl"
    pending_jsonl.write_text(_REAL_JSONL_3_TURNS, encoding="utf-8")

    ledger = tmp_path / "processed.tsv"
    ledger.write_text("", encoding="utf-8")

    calls: list[str] = []

    def subprocess_runner(cmd):
        joined = " ".join(str(c) for c in cmd)
        calls.append(joined)
        # Simulate refine success: append OK row to ledger, create session_md
        if "mnemos-refine-transcripts" in joined:
            sname = "2026-04-01-test.md"
            (sessions / sname).write_text(
                "---\ncwd: C:\\Projects\\farcry\n---\nbody\n", encoding="utf-8"
            )
            with ledger.open("a", encoding="utf-8") as fh:
                fh.write(f"{pending_jsonl}\tOK\t{sname}\n")
        return 0

    def brief_runner(cmd, stdout_path=None):
        if stdout_path is not None:
            Path(stdout_path).write_text("**Aktif durum:** caught up\n", encoding="utf-8")
        return 0

    inp = SessionStartInput(
        cwd="C:\\Projects\\farcry",
        source="startup",
        transcript_path="unrelated-live-session.jsonl",
    )

    result = handle_session_start(
        inp,
        vault=tmp_path,
        projects_root=tmp_path / ".claude" / "projects",
        ledger=ledger,
        subprocess_runner=subprocess_runner,
        brief_runner=brief_runner,
    )
    assert result.outcome == "sub_b2_catch_up_done"
    assert "**Aktif durum:** caught up" in result.injected_context

    # Refine + mine + brief all invoked
    assert any("mnemos-refine-transcripts" in c for c in calls)
    assert any("mnemos-mine-llm" in c for c in calls)


def test_sub_b2_refine_fails_skips_mine(tmp_path: Path) -> None:
    (tmp_path / "mnemos.yaml").write_text("recall_mode: skill\n", encoding="utf-8")
    (tmp_path / "Sessions").mkdir()
    slug = cwd_to_slug("C:\\x")
    state = CwdState()
    state.cwds[slug] = {"cwd": "C:\\x", "first_seen": 0.0, "last_seen": 0.0, "visit_count": 1}
    save_state(tmp_path, state)

    proj_root = tmp_path / ".claude" / "projects" / slug
    proj_root.mkdir(parents=True)
    pending = proj_root / "p.jsonl"
    pending.write_text(_REAL_JSONL_3_TURNS, encoding="utf-8")

    ledger = tmp_path / "processed.tsv"
    ledger.write_text("", encoding="utf-8")

    mine_called = [False]

    def subprocess_runner(cmd):
        if any("mnemos-mine-llm" in str(c) for c in cmd):
            mine_called[0] = True
        return 2  # refine fails

    def brief_runner(cmd, stdout_path=None):
        if stdout_path is not None:
            Path(stdout_path).write_text("**Aktif durum:** no sessions\n", encoding="utf-8")
        return 0

    inp = SessionStartInput(cwd="C:\\x", source="startup", transcript_path="y")
    result = handle_session_start(
        inp,
        vault=tmp_path,
        projects_root=tmp_path / ".claude" / "projects",
        ledger=ledger,
        subprocess_runner=subprocess_runner,
        brief_runner=brief_runner,
    )
    # Refine failed → mine should not run
    assert mine_called[0] is False
    # Briefing still runs on whatever was already in cache / prior sessions
    assert result.outcome in {"sub_b2_catch_up_done", "sub_b2_partial"}


def test_sub_b2_pending_is_capped_to_most_recent_N(tmp_path: Path) -> None:
    """A cwd with many unprocessed JSONLs should only sync-refine the last N.

    Regression: without the cap, a long-lived cwd (e.g. 300+ old sessions)
    blocked the hook for hours processing every historical JSONL. SUB-B2
    exists to freshen briefing context, not to catch up the entire backlog —
    that belongs to auto-refine's async cadence.
    """
    from mnemos.recall_briefing import SUB_B2_PENDING_CAP

    (tmp_path / "mnemos.yaml").write_text("recall_mode: skill\n", encoding="utf-8")
    (tmp_path / "Sessions").mkdir()
    slug = cwd_to_slug("C:\\big")
    state = CwdState()
    state.cwds[slug] = {"cwd": "C:\\big", "first_seen": 0.0, "last_seen": 0.0, "visit_count": 1}
    save_state(tmp_path, state)

    proj_root = tmp_path / ".claude" / "projects" / slug
    proj_root.mkdir(parents=True)
    # Create 50 JSONLs, mtime ascending. find_unrefined returns oldest-first,
    # cap logic takes the tail → most-recent N.
    import os as _os
    jsonls = []
    for i in range(50):
        j = proj_root / f"{i:03d}.jsonl"
        j.write_text(_REAL_JSONL_3_TURNS, encoding="utf-8")
        ts = 1_000_000 + i * 10  # monotonically increasing mtime
        _os.utime(j, (ts, ts))
        jsonls.append(j)

    ledger = tmp_path / "processed.tsv"
    ledger.write_text("", encoding="utf-8")

    refined_jsonls: list[str] = []

    def subprocess_runner(cmd):
        # Track which JSONL each refine call targets
        joined = " ".join(str(c) for c in cmd)
        if "mnemos-refine-transcripts" in joined:
            for a in cmd:
                if str(a).endswith(".jsonl"):
                    refined_jsonls.append(str(a))
                    # Also simulate ledger OK for this JSONL + session_md
                    jpath = str(a)
                    sname = f"{Path(jpath).stem}.md"
                    (tmp_path / "Sessions" / sname).write_text(
                        "---\ncwd: C:\\big\n---\nbody\n", encoding="utf-8"
                    )
                    with ledger.open("a", encoding="utf-8") as fh:
                        fh.write(f"{jpath}\tOK\t{sname}\n")
                    break
        return 0

    def brief_runner(cmd, stdout_path=None):
        if stdout_path is not None:
            Path(stdout_path).write_text("**Aktif durum:** brief\n", encoding="utf-8")
        return 0

    inp = SessionStartInput(cwd="C:\\big", source="startup", transcript_path="y")
    result = handle_session_start(
        inp,
        vault=tmp_path,
        projects_root=tmp_path / ".claude" / "projects",
        ledger=ledger,
        subprocess_runner=subprocess_runner,
        brief_runner=brief_runner,
    )

    # Refined count must not exceed SUB_B2_PENDING_CAP
    assert len(refined_jsonls) <= SUB_B2_PENDING_CAP, (
        f"refined {len(refined_jsonls)} JSONLs, expected ≤ {SUB_B2_PENDING_CAP}"
    )
    # The ones refined should be the N most-recent (by mtime) of 50 total
    refined_names = {Path(p).name for p in refined_jsonls}
    expected_most_recent = {f"{i:03d}.jsonl" for i in range(50 - SUB_B2_PENDING_CAP, 50)}
    assert refined_names == expected_most_recent, (
        f"got {refined_names}, expected most-recent {expected_most_recent}"
    )
    assert result.outcome == "sub_b2_catch_up_done"


# --- main entry ---

import io

from mnemos.recall_briefing import main


def test_main_parses_hook_input_and_emits_context(tmp_path: Path, capsys, monkeypatch) -> None:
    (tmp_path / "mnemos.yaml").write_text("recall_mode: skill\n", encoding="utf-8")
    (tmp_path / "Sessions").mkdir()

    slug = cwd_to_slug("C:\\Projects\\farcry")
    state = CwdState()
    state.cwds[slug] = {"cwd": "C:\\Projects\\farcry", "first_seen": 0.0, "last_seen": 0.0, "visit_count": 1}
    save_state(tmp_path, state)

    cache_p = cache_path_for(tmp_path, slug)
    write_cache(cache_p, body="**Aktif durum:** hi\n", cwd="C:\\Projects\\farcry", session_count=0, drawer_count=0)

    hook_input = json.dumps({
        "cwd": "C:\\Projects\\farcry",
        "source": "startup",
        "transcript_path": "/unrelated/path.jsonl",
    })
    monkeypatch.setattr("sys.stdin", io.StringIO(hook_input))
    monkeypatch.setenv("MNEMOS_VAULT", str(tmp_path))

    rc = main()
    assert rc == 0

    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert "hookSpecificOutput" in out
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "**Aktif durum:** hi" in out["hookSpecificOutput"]["additionalContext"]


def test_main_first_visit_emits_no_context(tmp_path: Path, capsys, monkeypatch) -> None:
    (tmp_path / "mnemos.yaml").write_text("recall_mode: skill\n", encoding="utf-8")

    hook_input = json.dumps({
        "cwd": "C:\\new-cwd-never-seen",
        "source": "startup",
        "transcript_path": "/x.jsonl",
    })
    monkeypatch.setattr("sys.stdin", io.StringIO(hook_input))
    monkeypatch.setenv("MNEMOS_VAULT", str(tmp_path))

    rc = main()
    assert rc == 0

    # First visit → no additionalContext emitted
    captured = capsys.readouterr()
    if captured.out.strip():
        out = json.loads(captured.out)
        if "hookSpecificOutput" in out:
            assert out["hookSpecificOutput"].get("additionalContext", "") == ""


def test_main_reentry_guard_exits_silently(tmp_path: Path, capsys, monkeypatch) -> None:
    """HOOK_ACTIVE_ENV set → main returns 0 before reading stdin or touching state.

    Protects against fork-bomb: our own claude --print subprocesses fire
    SessionStart hooks that re-invoke this main(). Without the guard,
    each re-invocation would spawn more subprocesses → unbounded recursion.
    """
    from mnemos.recall_briefing import HOOK_ACTIVE_ENV

    (tmp_path / "mnemos.yaml").write_text("recall_mode: skill\n", encoding="utf-8")
    monkeypatch.setenv("MNEMOS_VAULT", str(tmp_path))
    monkeypatch.setenv(HOOK_ACTIVE_ENV, "1")

    hook_input = json.dumps({
        "cwd": "C:\\Projects\\farcry",
        "source": "startup",
        "transcript_path": "/x.jsonl",
    })
    monkeypatch.setattr("sys.stdin", io.StringIO(hook_input))

    rc = main()
    assert rc == 0
    # No state written — we exit before touching the file
    assert not (tmp_path / ".mnemos-cwd-state.json").exists()
    captured = capsys.readouterr()
    assert captured.out.strip() == ""


def test_child_env_carries_reentry_marker_and_drops_api_key(monkeypatch) -> None:
    from mnemos.recall_briefing import _child_env, HOOK_ACTIVE_ENV

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    env = _child_env()
    assert env.get(HOOK_ACTIVE_ENV) == "1"
    assert "ANTHROPIC_API_KEY" not in env


def test_nt_no_window_flags_combines_no_window_and_detached() -> None:
    import os as _os
    if _os.name != "nt":
        return
    import subprocess as _sp
    from mnemos.recall_briefing import _nt_no_window_flags

    flags = _nt_no_window_flags()
    # Must include CREATE_NO_WINDOW so subprocess never flashes a terminal
    assert flags & _sp.CREATE_NO_WINDOW == _sp.CREATE_NO_WINDOW


# --- RC2: stdin UTF-8 decode (Windows cp1252 mojibake fix) ---

def test_main_stdout_handles_turkish_body_without_crash(tmp_path: Path, monkeypatch) -> None:
    """When injecting a Turkish briefing body, main() must not crash on the
    final print(). Windows default stdout is cp1252 — Turkish chars like
    ş/ğ/ü are NOT representable in cp1252 and cause UnicodeEncodeError on
    print(), which makes the hook exit 1 and causes Claude Code to silently
    drop the additionalContext. main() must reconfigure stdout to UTF-8.
    """
    (tmp_path / "mnemos.yaml").write_text("recall_mode: skill\n", encoding="utf-8")
    (tmp_path / "Sessions").mkdir()

    slug = cwd_to_slug("C:\\Projects\\test")
    state = CwdState()
    state.cwds[slug] = {"cwd": "C:\\Projects\\test", "first_seen": 0.0, "last_seen": 0.0, "visit_count": 1}
    save_state(tmp_path, state)

    # Cache body contains the exact Turkish char combinations from a real
    # brief: ş (ş), ğ (ğ), ü (ü). cp1252 maps none of these.
    turkish_body = (
        "**Aktif durum:** farcry klasörü boş; proje sıfırdan başlayacak. "
        "Davranış listesi ve teknoloji seçimi kullanıcı yanıtını bekliyor.\n"
    )
    cache = cache_path_for(tmp_path, slug)
    write_cache(cache, body=turkish_body, cwd="C:\\Projects\\test",
                session_count=0, drawer_count=0)

    hook_input = json.dumps({
        "cwd": "C:\\Projects\\test",
        "source": "startup",
        "transcript_path": "/unrelated/live.jsonl",
    })
    monkeypatch.setattr("sys.stdin", io.StringIO(hook_input))
    monkeypatch.setenv("MNEMOS_VAULT", str(tmp_path))

    # Replace stdout with a cp1252 writer — what Windows gives by default
    fake_out = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", newline="")
    monkeypatch.setattr("sys.stdout", fake_out)

    # Must not raise UnicodeEncodeError
    rc = main()
    assert rc == 0

    fake_out.flush()
    raw = fake_out.buffer.getvalue()
    # After the fix the body is emitted as UTF-8 bytes — the Turkish "ş"
    # byte pattern (\xc5\x9f) should be visible
    assert b"\xc5\x9f" in raw or b"\xc4\x9f" in raw or b"\xc3\xbc" in raw, (
        f"No UTF-8 Turkish byte sequence in stdout; got {raw[:200]!r}"
    )


def test_main_decodes_utf8_stdin_without_mojibake(tmp_path: Path, monkeypatch, capsys) -> None:
    """Claude Code sends SessionStart payload as UTF-8 JSON on stdin.
    Windows Python defaults stdin to cp1252 — UTF-8 'ü' (C3 BC) becomes 'Ã¼'.
    main() must reconfigure stdin to UTF-8 so non-ASCII cwds stay intact.
    Without the fix: state.json cwd field stores mojibake, slug mismatches
    Claude Code's project dir, and SUB-B2 never triggers for these cwds.
    """
    (tmp_path / "mnemos.yaml").write_text("recall_mode: skill\n", encoding="utf-8")

    payload_bytes = json.dumps({
        "cwd": "C:\\Users\\u\\Masaüstü\\test",
        "source": "startup",
        "transcript_path": "",
    }, ensure_ascii=False).encode("utf-8")

    # Mimic Windows: stdin wraps raw bytes via cp1252 codec. If main() doesn't
    # reconfigure to UTF-8 before reading, 'ü' will surface as 'Ã¼'.
    fake_stdin = io.TextIOWrapper(
        io.BytesIO(payload_bytes), encoding="cp1252", newline="",
    )
    monkeypatch.setattr("sys.stdin", fake_stdin)
    monkeypatch.setenv("MNEMOS_VAULT", str(tmp_path))

    rc = main()
    assert rc == 0

    # State should store the clean UTF-8 cwd, not cp1252 mojibake
    state = load_state(tmp_path)
    assert state.cwds, "main() did not record state — stdin never parsed"
    for slug, info in state.cwds.items():
        assert "Ã" not in info["cwd"], (
            f"mojibake detected in stored cwd {info['cwd']!r} (slug={slug!r}) — "
            f"stdin was not decoded as UTF-8"
        )


# --- RC3: brief_and_cache subcommand (bg spawn actually produces cache) ---

def test_brief_and_cache_writes_cache_from_briefing_skill(tmp_path: Path) -> None:
    """brief_and_cache() runs the briefing skill and persists the result to
    <vault>/.mnemos-briefings/<slug>.md. This replaces the old _spawn_bg_brief
    pattern which redirected subprocess stdout to DEVNULL — briefing body was
    discarded, cache was never created, and SUB-B1 no-cache path stayed
    permanently in no-cache state across every visit.
    """
    from mnemos.recall_briefing import brief_and_cache

    cwd = "C:\\Users\\u\\TestProject"
    fake_body = "**Aktif durum:** test briefing body.\n"

    def fake_runner(cmd, stdout_path=None):
        if stdout_path is not None:
            Path(stdout_path).write_text(fake_body, encoding="utf-8")
        return 0

    ok = brief_and_cache(cwd=cwd, vault=tmp_path, brief_runner=fake_runner)
    assert ok is True

    cache = cache_path_for(tmp_path, cwd_to_slug(cwd))
    assert cache.exists(), "brief_and_cache did not write cache file"
    text = cache.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "cache missing frontmatter"
    assert "**Aktif durum:**" in text
    assert f"cwd: {cwd}" in text


def test_brief_and_cache_failure_does_not_write_empty_cache(tmp_path: Path) -> None:
    """If the briefing skill exits non-zero or emits empty body, cache must
    NOT be written — otherwise a fresh-enough but empty cache would be
    injected in place of real briefings forever after.
    """
    from mnemos.recall_briefing import brief_and_cache

    cwd = "C:\\x"
    ok = brief_and_cache(cwd=cwd, vault=tmp_path, brief_runner=lambda cmd, stdout_path=None: 2)
    assert ok is False
    assert not cache_path_for(tmp_path, cwd_to_slug(cwd)).exists()


def test_spawn_bg_brief_uses_brief_and_cache_subcommand(tmp_path: Path, monkeypatch) -> None:
    """Bg brief subprocess must invoke the --brief-and-cache entry of
    mnemos.recall_briefing (which calls brief_and_cache internally) — NOT
    claude --print with stdout=DEVNULL directly. The old pattern spawned a
    briefing but discarded the body via DEVNULL, never creating cache.
    """
    from mnemos.recall_briefing import _spawn_bg_brief

    captured: list[tuple[list[str], dict]] = []

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            captured.append((list(cmd), dict(kwargs)))

    import subprocess as _sp
    monkeypatch.setattr(_sp, "Popen", FakePopen)

    _spawn_bg_brief("C:\\x", vault=tmp_path)

    assert len(captured) == 1
    cmd, _ = captured[0]
    joined = " ".join(cmd)
    # Must invoke our brief-and-cache entry, not claude --print directly
    assert "mnemos.recall_briefing" in joined or "recall_briefing" in joined
    assert "--brief-and-cache" in joined
    assert "C:\\x" in joined
    assert str(tmp_path) in joined


def test_main_brief_and_cache_mode_invokes_brief_and_cache(tmp_path: Path, monkeypatch) -> None:
    """Parent hook spawns `python -m mnemos.recall_briefing --brief-and-cache
    --cwd X --vault Y`. When main() receives these flags it must call
    brief_and_cache(X, Y) and exit WITHOUT touching stdin / state / hook logic.
    """
    called: list[tuple[str, Path]] = []

    def fake_brief_and_cache(cwd, vault, brief_runner=None):
        called.append((cwd, vault))
        return True

    monkeypatch.setattr("mnemos.recall_briefing.brief_and_cache", fake_brief_and_cache)

    (tmp_path / "mnemos.yaml").write_text("recall_mode: skill\n", encoding="utf-8")

    # stdin should NEVER be consumed in this mode; make it obvious if it is
    def fail_stdin_read():
        raise AssertionError("brief-and-cache mode must not read stdin")
    fake_stdin = type("S", (), {"read": staticmethod(fail_stdin_read)})()
    monkeypatch.setattr("sys.stdin", fake_stdin)

    rc = main(["--brief-and-cache", "--cwd", "C:\\Projects\\foo", "--vault", str(tmp_path)])
    assert rc == 0
    assert called == [("C:\\Projects\\foo", tmp_path)]
