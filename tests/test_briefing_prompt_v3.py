"""v1.1 briefing prompt v3 structure verification + junction zero-drift."""
from __future__ import annotations

from pathlib import Path

PROMPT = Path(__file__).parent.parent / "skills" / "mnemos-briefing" / "prompt.md"


def test_prompt_v3_has_all_steps():
    text = PROMPT.read_text(encoding="utf-8")
    assert "## STEP 0 — Read previous brief" in text
    assert "## STEP 1 — Identity layer" in text
    assert "## STEP 2A — All cwd Sessions" in text
    assert "## STEP 2B — Recent 5 cwd Sessions" in text
    assert "## STEP 3 — Cross-context backlinks" in text
    assert "## STEP 4 — Token budget" in text
    assert "## STEP 5 — Synthesize" in text


def test_prompt_v3_revision_directive_present():
    text = PROMPT.read_text(encoding="utf-8")
    assert "Revision marking" in text or "Revize" in text
    assert "Anchor preservation" in text


def test_prompt_v3_token_cap_25k():
    text = PROMPT.read_text(encoding="utf-8")
    assert "25K" in text and "HARD CAP" in text


def test_briefing_prompt_junction_zero_drift():
    repo = Path(__file__).parent.parent / "skills" / "mnemos-briefing" / "prompt.md"
    junction = Path.home() / ".claude" / "skills" / "mnemos-briefing" / "prompt.md"
    if not junction.exists():
        import pytest
        pytest.skip("junction not installed")
    assert repo.read_bytes() == junction.read_bytes()
