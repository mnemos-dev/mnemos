"""Tests for mnemos.recall_briefing — cwd-aware SessionStart briefing hook."""
from __future__ import annotations

import json
from pathlib import Path

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


def test_slug_unicode_preserved_via_word_class() -> None:
    # Turkish chars are word-class in \w if re.UNICODE (default in py3)
    assert cwd_to_slug("C:\\Projects\\Masaüstü") == "C--Projects-Masaüstü"


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
    jsonl_old.write_text("{}\n", encoding="utf-8")
    jsonl_new.write_text("{}\n", encoding="utf-8")

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
