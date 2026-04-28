"""Tests for refine-transcripts.md v2 prompt rules."""
from pathlib import Path


PROMPT_PATH = Path(__file__).parent.parent / "docs" / "prompts" / "refine-transcripts.md"


def test_prompt_documents_tag_prefix_categories():
    """v2 prompt must list all 5 tag prefix categories."""
    content = PROMPT_PATH.read_text(encoding="utf-8")
    for prefix in ["proj/", "tool/", "person/", "file/", "skill/"]:
        assert prefix in content, f"Missing tag prefix category: {prefix}"


def test_prompt_documents_wikilink_inclusion_rules():
    """v2 prompt must document which prose entities become wikilinks
    and which do not."""
    content = PROMPT_PATH.read_text(encoding="utf-8")
    assert "Becomes a wikilink" in content
    assert "Does NOT become a wikilink" in content


def test_prompt_documents_quality_control_checklist():
    """v2 prompt must include the post-write QUALITY CONTROL checklist."""
    content = PROMPT_PATH.read_text(encoding="utf-8")
    assert "QUALITY CONTROL" in content
    assert "at least 1 `proj/*` tag" in content
    assert "at least 1 wikilink in prose" in content
