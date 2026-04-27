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


# Carried over from the retired test_briefing_v2.py — assertions still
# relevant to v3 (recency/relevance scoring is retained in STEP 3, the user
# profile section persists in STEP 5 output, and SKILL.md still references
# the layered flow).


def test_prompt_documents_recency_relevance_sorting():
    text = PROMPT.read_text(encoding="utf-8")
    assert "recency" in text.lower() or "date desc" in text.lower()
    assert "relevance" in text.lower() or "overlap" in text.lower()


def test_prompt_output_includes_user_profile_section():
    text = PROMPT.read_text(encoding="utf-8")
    assert "Kullanıcı profili" in text


SKILL_PATH = Path(__file__).parent.parent / "skills" / "mnemos-briefing" / "SKILL.md"


def test_skill_md_references_layered_flow():
    text = SKILL_PATH.read_text(encoding="utf-8")
    assert "Identity" in text
    assert "Cross-context" in text or "cross-context" in text
