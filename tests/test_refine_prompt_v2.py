"""Tests for refine-transcripts.md v2 prompt rules."""
from pathlib import Path


PROMPT_PATH = Path(__file__).parent.parent / "docs" / "prompts" / "refine-transcripts.md"


def test_prompt_documents_tag_prefix_categories():
    """v2 prompt must list all 5 tag prefix categories."""
    content = PROMPT_PATH.read_text(encoding="utf-8")
    for prefix in ["proj/", "tool/", "person/", "file/", "skill/"]:
        assert prefix in content, f"Missing tag prefix category: {prefix}"


def test_prompt_documents_wikilink_inclusion_rules():
    """v2 prompt must explicitly say 'wikilink olur' and 'wikilink olmaz' rules."""
    content = PROMPT_PATH.read_text(encoding="utf-8")
    assert "Wikilink olur" in content or "wikilink olur" in content
    assert "Wikilink olmaz" in content or "wikilink olmaz" in content


def test_prompt_documents_quality_control_checklist():
    """v2 prompt must include post-write quality control checklist."""
    content = PROMPT_PATH.read_text(encoding="utf-8")
    assert "En az 1 `proj/*` tag'i" in content or "En az 1 proj/" in content
    assert "En az 1 wikilink prose" in content
