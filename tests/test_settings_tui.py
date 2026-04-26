"""Settings TUI tests — render, validators, apply, per-cwd breakdown, progress."""
from __future__ import annotations

from pathlib import Path

import pytest


def test_render_menu_includes_all_section_headers(tmp_path):
    from mnemos.settings_tui import render_menu

    (tmp_path / "mnemos.yaml").write_text(
        "schema_version: 2\nsearch_backend: sqlite-vec\n", encoding="utf-8"
    )
    output = render_menu(vault=tmp_path)
    assert "Refine pipeline:" in output
    assert "Briefing:" in output
    assert "Identity:" in output
    assert "Hooks" in output
    assert "Backend & locale:" in output
    assert "Refinement Progress" in output


def test_render_menu_shows_current_values(tmp_path):
    from mnemos.settings_tui import render_menu

    (tmp_path / "mnemos.yaml").write_text(
        "schema_version: 2\nsearch_backend: sqlite-vec\n"
        "refine:\n  per_session: 15\n  direction: oldest\n",
        encoding="utf-8",
    )
    output = render_menu(vault=tmp_path)
    assert "15" in output
    assert "oldest" in output
    assert "sqlite-vec" in output


def test_format_field_line_aligns():
    from mnemos.settings_tui import _format_field_line

    line = _format_field_line(num=1, label="JSONLs per session start", value="3")
    assert line.startswith("  1)")
    assert "3" in line


def test_validate_int_field_in_range():
    from mnemos.settings_tui import validate_int

    assert validate_int("5", min_v=1, max_v=10) == (True, 5, "")
    assert validate_int("100", min_v=1, max_v=10)[0] is False
    assert validate_int("abc", min_v=1, max_v=10)[0] is False
    assert validate_int("0", min_v=1, max_v=10)[0] is False


def test_validate_bool_field():
    from mnemos.settings_tui import validate_bool

    ok, val, _ = validate_bool("true")
    assert ok and val is True
    assert validate_bool("y")[1] is True
    assert validate_bool("false")[1] is False
    assert validate_bool("xyz")[0] is False


def test_validate_choice_field():
    from mnemos.settings_tui import validate_choice

    assert validate_choice("newest", ["newest", "oldest"]) == (True, "newest", "")
    assert validate_choice("middle", ["newest", "oldest"])[0] is False


def test_apply_field_change_updates_cfg():
    from mnemos.settings_tui import apply_field_change
    from mnemos.config import MnemosConfig

    cfg = MnemosConfig(vault_path="/x")
    assert cfg.refine.per_session == 3
    apply_field_change(cfg, field_num=1, value=15)
    assert cfg.refine.per_session == 15

    apply_field_change(cfg, field_num=2, value="oldest")
    assert cfg.refine.direction == "oldest"

    apply_field_change(cfg, field_num=5, value=False)
    assert cfg.briefing.show_systemmessage is False

    apply_field_change(cfg, field_num=15, value="sqlite-vec")
    assert cfg.search_backend == "sqlite-vec"
