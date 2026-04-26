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
