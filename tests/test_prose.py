"""Tests for mnemos.prose — code line filtering / prose extraction."""
from __future__ import annotations

import pytest

from mnemos.prose import extract_prose


# ---------------------------------------------------------------------------
# Core requirements (from spec)
# ---------------------------------------------------------------------------


def test_removes_code_blocks():
    text = (
        "Important decision here.\n\n"
        "```python\n"
        "def foo():\n"
        "    return 42\n"
        "```\n\n"
        "Another fact."
    )
    result = extract_prose(text)
    assert "def foo" not in result
    assert "Important decision" in result
    assert "Another fact" in result


def test_removes_shell_commands():
    text = (
        "We decided to deploy.\n"
        "$ git push origin main\n"
        "$ npm install\n"
        "Deployment complete."
    )
    result = extract_prose(text)
    assert "git push" not in result
    assert "npm install" not in result
    assert "decided to deploy" in result


def test_removes_import_statements():
    text = (
        "The module works.\n"
        "import os\n"
        "from pathlib import Path\n"
        "All tests pass."
    )
    result = extract_prose(text)
    assert "import os" not in result
    assert "module works" in result


def test_removes_low_alpha_lines():
    text = (
        "Good line here.\n"
        ">>>>>>>>>>>>>>>>>\n"
        "{'key': 123, 'val': 456}\n"
        "Another good line."
    )
    result = extract_prose(text)
    assert ">>>>>" not in result
    assert "Good line" in result


def test_preserves_prose_only():
    text = (
        "We chose React for the frontend.\n"
        "It was a tough decision but the ecosystem won us over."
    )
    result = extract_prose(text)
    assert "chose React" in result


def test_empty_input():
    assert extract_prose("") == ""


def test_all_code_returns_empty():
    text = "import os\nimport sys\ndef main():\n    pass"
    result = extract_prose(text)
    assert result.strip() == ""


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_removes_fenced_code_block_no_language():
    text = "Here is some context.\n\n```\necho hello\n```\n\nEnd of note."
    result = extract_prose(text)
    assert "echo hello" not in result
    assert "context" in result
    assert "End of note" in result


def test_removes_fenced_code_block_multiline():
    text = (
        "Decision taken.\n\n"
        "```javascript\n"
        "const x = 1;\n"
        "const y = 2;\n"
        "console.log(x + y);\n"
        "```\n\n"
        "Discussion continued."
    )
    result = extract_prose(text)
    assert "const x" not in result
    assert "console.log" not in result
    assert "Decision taken" in result
    assert "Discussion continued" in result


def test_removes_class_and_return():
    text = (
        "Architecture was discussed.\n"
        "class MyClass:\n"
        "    def method(self):\n"
        "        return True\n"
        "Outcome was positive."
    )
    result = extract_prose(text)
    assert "class MyClass" not in result
    assert "return True" not in result
    assert "Architecture" in result
    assert "Outcome" in result


def test_removes_docker_commands():
    text = (
        "Containerisation decided.\n"
        "docker build -t myapp .\n"
        "docker run -p 8080:8080 myapp\n"
        "Services are now running."
    )
    result = extract_prose(text)
    assert "docker build" not in result
    assert "docker run" not in result
    assert "Containerisation" in result


def test_removes_cd_and_pip():
    text = (
        "Setup instructions noted.\n"
        "cd /home/user/project\n"
        "pip install -r requirements.txt\n"
        "Environment is ready."
    )
    result = extract_prose(text)
    assert "pip install" not in result
    assert "cd /home" not in result
    assert "Setup instructions" in result


def test_collapses_multiple_blank_lines():
    text = "First sentence.\n\n\n\n\nSecond sentence."
    result = extract_prose(text)
    assert "First sentence" in result
    assert "Second sentence" in result
    # Should not have more than one consecutive blank line
    assert "\n\n\n" not in result


def test_prose_with_numbers_preserved():
    """Lines with enough alphabetic content survive even with numbers."""
    text = "We released version 2.0 on April 10th.\nIt was a major milestone."
    result = extract_prose(text)
    assert "We released version" in result
    assert "major milestone" in result


def test_pure_punctuation_line_removed():
    """Lines that are almost entirely punctuation / symbols are dropped."""
    text = "Valid sentence here.\n-------------------\nAnother valid sentence."
    result = extract_prose(text)
    assert "---" not in result
    assert "Valid sentence" in result


def test_git_command_without_dollar():
    """git/npm/pip commands without $ prefix are also removed."""
    text = "We made a choice.\ngit commit -m 'init'\npip install flask\nChoice confirmed."
    result = extract_prose(text)
    assert "git commit" not in result
    assert "pip install" not in result
    assert "We made a choice" in result


def test_single_prose_line():
    text = "This is a single clean sentence."
    result = extract_prose(text)
    assert "single clean sentence" in result


def test_mixed_content_preserves_prose_paragraphs():
    text = (
        "Team decided to use PostgreSQL.\n\n"
        "```sql\n"
        "SELECT * FROM users WHERE active = true;\n"
        "```\n\n"
        "import psycopg2\n\n"
        "The migration ran successfully."
    )
    result = extract_prose(text)
    assert "PostgreSQL" in result
    assert "migration ran successfully" in result
    assert "SELECT *" not in result
    assert "import psycopg2" not in result
