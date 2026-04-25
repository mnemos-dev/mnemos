"""Sanity checks for the mnemos-recall skill package.

Two guarantees:
  1. SKILL.md has a parseable YAML frontmatter with name + description.
  2. If ~/.claude/skills/mnemos-recall is installed as a junction, its
     SKILL.md byte-matches the repo copy (zero drift).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mnemos.obsidian import parse_frontmatter


REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_MD = REPO_ROOT / "skills" / "mnemos-recall" / "SKILL.md"


def test_mnemos_recall_skill_frontmatter_valid():
    assert SKILL_MD.is_file(), f"Expected SKILL.md at {SKILL_MD}"

    frontmatter, _body = parse_frontmatter(SKILL_MD)

    assert frontmatter.get("name") == "mnemos-recall", (
        "frontmatter.name must be 'mnemos-recall' for Claude Code slash "
        "command discovery"
    )

    description = frontmatter.get("description", "")
    assert isinstance(description, str) and len(description) >= 50, (
        "frontmatter.description must be a non-trivial string "
        "(skill discovery ranks on it)"
    )


def test_mnemos_recall_skill_junction_zero_drift():
    junction = Path.home() / ".claude" / "skills" / "mnemos-recall" / "SKILL.md"

    if not junction.exists():
        pytest.skip(
            "Junction not installed in user home — dev-workflow check only"
        )

    assert junction.read_bytes() == SKILL_MD.read_bytes(), (
        "Junction has drifted from repo SKILL.md — re-create the junction"
    )


def test_skill_uses_collection_raw_only():
    """v1.0: SKILL.md must specify collection='raw' (not 'both' or 'mined')."""
    skill_path = Path(__file__).parent.parent / "skills" / "mnemos-recall" / "SKILL.md"
    content = skill_path.read_text(encoding="utf-8")
    assert 'collection="raw"' in content
    assert 'collection="both"' not in content
    assert 'collection="mined"' not in content


def test_skill_documents_threshold_calibration_note():
    skill_path = Path(__file__).parent.parent / "skills" / "mnemos-recall" / "SKILL.md"
    content = skill_path.read_text(encoding="utf-8")
    assert "0.015" in content
    assert "kalibre" in content.lower() or "calibrat" in content.lower()
