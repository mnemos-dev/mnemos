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
