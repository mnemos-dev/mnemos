"""Tests for v2 briefing skill prompt structure."""
from pathlib import Path

PROMPT_PATH = Path(__file__).parent.parent / "skills" / "mnemos-briefing" / "prompt.md"
SKILL_PATH = Path(__file__).parent.parent / "skills" / "mnemos-briefing" / "SKILL.md"


def test_prompt_documents_3_layers():
    content = PROMPT_PATH.read_text(encoding="utf-8")
    assert "Identity Layer" in content
    assert "Cwd Layer" in content
    assert "Cross-context Layer" in content


def test_prompt_documents_priority_budget():
    content = PROMPT_PATH.read_text(encoding="utf-8")
    assert "3K" in content  # Identity budget
    assert "8K" in content  # Cwd budget
    assert "4K" in content  # Cross-context budget
    assert "15K" in content  # total cap


def test_prompt_documents_recency_relevance_sorting():
    content = PROMPT_PATH.read_text(encoding="utf-8")
    assert "recency" in content.lower() or "date desc" in content.lower()
    assert "relevance" in content.lower() or "overlap" in content.lower()


def test_prompt_output_includes_user_profile_section():
    content = PROMPT_PATH.read_text(encoding="utf-8")
    assert "Kullanıcı profili" in content


def test_skill_md_references_3_layer_flow():
    content = SKILL_PATH.read_text(encoding="utf-8")
    assert "Identity" in content
    assert "Cross-context" in content or "cross-context" in content
