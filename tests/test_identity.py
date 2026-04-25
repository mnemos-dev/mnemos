"""Identity Layer tests."""
from pathlib import Path

PROMPT_PATH = Path(__file__).parent.parent / "docs" / "prompts" / "identity-bootstrap.md"


def test_identity_bootstrap_prompt_exists():
    assert PROMPT_PATH.exists(), f"Missing canonical prompt: {PROMPT_PATH}"


def test_identity_bootstrap_prompt_documents_sections():
    content = PROMPT_PATH.read_text(encoding="utf-8")
    for section in [
        "Çalışma stili",
        "Teknik tercihler",
        "Reddedilen yaklaşımlar",
        "Aktif projeler",
        "Yörüngedeki insanlar",
        "Ustalaşmış araçlar",
        "Revize edilen kararlar",
    ]:
        assert section in content, f"Missing section: {section}"


def test_identity_bootstrap_prompt_documents_scope_notation():
    content = PROMPT_PATH.read_text(encoding="utf-8")
    assert "(general)" in content
    assert "(proj/" in content


def test_identity_bootstrap_prompt_documents_size_limits():
    content = PROMPT_PATH.read_text(encoding="utf-8")
    assert "max" in content.lower() and "madde" in content.lower()


def test_identity_bootstrap_prompt_documents_context_cap():
    content = PROMPT_PATH.read_text(encoding="utf-8")
    assert "150K" in content or "150000" in content
