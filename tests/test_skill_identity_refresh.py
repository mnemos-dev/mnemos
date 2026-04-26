# tests/test_skill_identity_refresh.py
from pathlib import Path
import re


REPO_SKILL = Path(__file__).parent.parent / "skills" / "mnemos-identity-refresh"
JUNCTION_SKILL = Path.home() / ".claude" / "skills" / "mnemos-identity-refresh"


def test_skill_md_frontmatter_valid():
    md = (REPO_SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert md.startswith("---\n"), "SKILL.md must start with frontmatter"
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", md, re.DOTALL)
    assert m, "SKILL.md frontmatter unparseable"
    front = m.group(1)
    assert "name: mnemos-identity-refresh" in front
    assert "description:" in front


def test_prompt_md_exists_and_nonempty():
    prompt = (REPO_SKILL / "prompt.md").read_text(encoding="utf-8")
    assert len(prompt) > 100
    assert "## CLASSIFICATION DISCIPLINE" in prompt or "## DELTA RULES" in prompt


def test_junction_zero_drift():
    """Repo SKILL.md and junction-visible SKILL.md must be byte-identical."""
    if not JUNCTION_SKILL.exists():
        import pytest
        pytest.skip(f"junction not installed: {JUNCTION_SKILL}")
    repo_bytes = (REPO_SKILL / "SKILL.md").read_bytes()
    junction_bytes = (JUNCTION_SKILL / "SKILL.md").read_bytes()
    assert repo_bytes == junction_bytes, "junction drift detected"
