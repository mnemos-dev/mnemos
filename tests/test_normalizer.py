"""Tests for mnemos.normalizer — 5-format conversation normalizer."""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from mnemos.normalizer import detect_format, normalize_file, normalize_text


# ---------------------------------------------------------------------------
# detect_format
# ---------------------------------------------------------------------------


def test_detect_claude_code_jsonl():
    lines = [
        json.dumps({"type": "human", "message": {"content": "Hello"}}),
        json.dumps({"type": "assistant", "message": {"content": "Hi"}}),
    ]
    assert detect_format("\n".join(lines)) == "claude_code_jsonl"


def test_detect_chatgpt_json():
    data = {
        "title": "Chat",
        "mapping": {
            "node1": {
                "message": {
                    "author": {"role": "user"},
                    "content": {"parts": ["Hello"]},
                }
            }
        },
    }
    assert detect_format(json.dumps(data)) == "chatgpt_json"


def test_detect_slack_json():
    data = [{"type": "message", "user": "U123", "text": "Hello"}]
    assert detect_format(json.dumps(data)) == "slack_json"


def test_detect_plain_text():
    assert detect_format("Just some regular text.") == "plain_text"


def test_detect_empty_string():
    assert detect_format("") == "plain_text"


def test_detect_plain_text_markdown():
    md = "# Heading\n\nSome **bold** text and a list:\n- item 1\n- item 2"
    assert detect_format(md) == "plain_text"


def test_detect_json_array_not_slack():
    """A JSON array whose first element lacks type:message → plain_text."""
    data = [{"id": 1, "value": "x"}]
    assert detect_format(json.dumps(data)) == "plain_text"


def test_detect_json_object_without_mapping():
    """A JSON object without 'mapping' key → plain_text."""
    data = {"title": "Chat", "messages": []}
    assert detect_format(json.dumps(data)) == "plain_text"


# ---------------------------------------------------------------------------
# normalize_text — Claude Code JSONL
# ---------------------------------------------------------------------------


def test_normalize_claude_code_jsonl_basic():
    lines = [
        json.dumps({"type": "human", "message": {"content": "What is RLS?"}}),
        json.dumps({"type": "assistant", "message": {"content": "Row Level Security is..."}}),
    ]
    result = normalize_text("\n".join(lines))
    assert "> What is RLS?" in result
    assert "Row Level Security" in result


def test_normalize_claude_code_jsonl_structure():
    lines = [
        json.dumps({"type": "human", "message": {"content": "Hello"}}),
        json.dumps({"type": "assistant", "message": {"content": "Hi there"}}),
    ]
    result = normalize_text("\n".join(lines))
    assert result.startswith("> Hello")
    assert "Hi there" in result


def test_normalize_claude_code_jsonl_with_tool_blocks():
    """Tool use + tool result + text in assistant message."""
    content_blocks = [
        {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls"}},
        {"type": "tool_result", "tool_use_id": "t1", "content": "file1.py\nfile2.py"},
        {"type": "text", "text": "Found 2 files."},
    ]
    lines = [
        json.dumps({"type": "human", "message": {"content": "List files"}}),
        json.dumps({"type": "assistant", "message": {"content": content_blocks}}),
    ]
    result = normalize_text("\n".join(lines))
    assert "> List files" in result
    assert "Bash" in result
    assert "Found 2 files." in result


def test_normalize_claude_code_jsonl_list_content():
    """Content as list with a single text block."""
    content_blocks = [{"type": "text", "text": "Sure, I can help."}]
    lines = [
        json.dumps({"type": "human", "message": {"content": "Help me"}}),
        json.dumps({"type": "assistant", "message": {"content": content_blocks}}),
    ]
    result = normalize_text("\n".join(lines))
    assert "Sure, I can help." in result


# ---------------------------------------------------------------------------
# normalize_text — ChatGPT JSON
# ---------------------------------------------------------------------------


def _build_chatgpt_export(pairs: list[tuple[str, str]]) -> str:
    """Build a minimal ChatGPT-style JSON export from (role, text) pairs."""
    mapping: dict = {
        "root": {"id": "root", "parent": None, "children": [], "message": None}
    }
    prev_id = "root"
    node_ids = []
    for i, (role, text) in enumerate(pairs):
        node_id = f"msg{i}"
        mapping[node_id] = {
            "id": node_id,
            "parent": prev_id,
            "children": [],
            "message": {
                "author": {"role": role},
                "content": {"parts": [text]},
            },
        }
        mapping[prev_id]["children"].append(node_id)
        prev_id = node_id
        node_ids.append(node_id)
    return json.dumps({"title": "Test chat", "mapping": mapping})


def test_normalize_chatgpt_basic():
    export = _build_chatgpt_export([("user", "Hello"), ("assistant", "Hi!")])
    result = normalize_text(export)
    assert "> Hello" in result
    assert "Hi!" in result


def test_normalize_chatgpt_order():
    """Messages should appear in tree order."""
    export = _build_chatgpt_export(
        [("user", "First"), ("assistant", "Second"), ("user", "Third")]
    )
    result = normalize_text(export)
    assert result.index("First") < result.index("Second") < result.index("Third")


def test_normalize_chatgpt_skips_system():
    """System-role messages should not appear in output."""
    mapping: dict = {
        "root": {"id": "root", "parent": None, "children": ["sys", "u1"], "message": None},
        "sys": {
            "id": "sys",
            "parent": "root",
            "children": [],
            "message": {"author": {"role": "system"}, "content": {"parts": ["You are a helpful assistant."]}},
        },
        "u1": {
            "id": "u1",
            "parent": "root",
            "children": [],
            "message": {"author": {"role": "user"}, "content": {"parts": ["Hi"]}},
        },
    }
    result = normalize_text(json.dumps({"title": "Chat", "mapping": mapping}))
    assert "You are a helpful assistant." not in result
    assert "> Hi" in result


# ---------------------------------------------------------------------------
# normalize_text — Slack JSON
# ---------------------------------------------------------------------------


def test_normalize_slack_basic():
    data = [
        {"type": "message", "user": "U001", "text": "Hey team"},
        {"type": "message", "user": "U002", "text": "Hello!"},
    ]
    result = normalize_text(json.dumps(data))
    assert "> Hey team" in result
    assert "Hello!" in result


def test_normalize_slack_first_speaker_is_user():
    """First unique user gets > prefix, others are treated as assistant."""
    data = [
        {"type": "message", "user": "U001", "text": "Question?"},
        {"type": "message", "user": "U002", "text": "Answer."},
        {"type": "message", "user": "U001", "text": "Follow-up?"},
    ]
    result = normalize_text(json.dumps(data))
    lines = result.split("\n\n")
    assert lines[0].startswith("> Question?")
    assert not lines[1].startswith(">")
    assert lines[2].startswith("> Follow-up?")


def test_normalize_slack_skips_empty_messages():
    data = [
        {"type": "message", "user": "U001", "text": "Real message"},
        {"type": "message", "user": "U002", "text": ""},
        {"type": "message", "user": "U002", "text": "  "},
        {"type": "message", "user": "U002", "text": "Response"},
    ]
    result = normalize_text(json.dumps(data))
    assert "> Real message" in result
    assert "Response" in result
    # No double blank segments from empty messages
    assert "\n\n\n\n" not in result


# ---------------------------------------------------------------------------
# normalize_text — plain text passthrough
# ---------------------------------------------------------------------------


def test_normalize_plain_passthrough():
    text = "Regular markdown."
    assert normalize_text(text) == text


def test_normalize_plain_passthrough_multiline():
    text = "Line 1\nLine 2\nLine 3"
    assert normalize_text(text) == text


# ---------------------------------------------------------------------------
# Merge consecutive assistant messages
# ---------------------------------------------------------------------------


def test_merge_consecutive_assistant():
    """Two consecutive assistant messages are merged into one block."""
    content1 = [{"type": "text", "text": "Part one."}]
    content2 = [{"type": "text", "text": "Part two."}]
    lines = [
        json.dumps({"type": "human", "message": {"content": "Tell me something"}}),
        json.dumps({"type": "assistant", "message": {"content": content1}}),
        json.dumps({"type": "assistant", "message": {"content": content2}}),
    ]
    result = normalize_text("\n".join(lines))
    # Should only be two segments: > user and merged assistant
    segments = result.split("\n\n")
    assert len(segments) == 2
    assert "Part one." in segments[1]
    assert "Part two." in segments[1]


def test_merge_three_consecutive_assistant():
    lines = [
        json.dumps({"type": "human", "message": {"content": "Q"}}),
        json.dumps({"type": "assistant", "message": {"content": "A1"}}),
        json.dumps({"type": "assistant", "message": {"content": "A2"}}),
        json.dumps({"type": "assistant", "message": {"content": "A3"}}),
    ]
    result = normalize_text("\n".join(lines))
    segments = result.split("\n\n")
    assert len(segments) == 2
    assert "A1" in segments[1] and "A2" in segments[1] and "A3" in segments[1]


# ---------------------------------------------------------------------------
# Tool result truncation
# ---------------------------------------------------------------------------


def test_tool_result_truncation():
    """100-line tool result is truncated to ~40 lines (first 20 + last 20)."""
    big_output = "\n".join(f"line{i}" for i in range(100))
    content_blocks = [
        {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls -la"}},
        {"type": "tool_result", "tool_use_id": "t1", "content": big_output},
        {"type": "text", "text": "Done."},
    ]
    lines = [
        json.dumps({"type": "human", "message": {"content": "Run ls"}}),
        json.dumps({"type": "assistant", "message": {"content": content_blocks}}),
    ]
    result = normalize_text("\n".join(lines))
    # Should contain truncation marker
    assert "omitted" in result
    # Should contain first line
    assert "line0" in result
    # Should contain last line
    assert "line99" in result
    # Should NOT contain middle lines
    assert "line50" not in result


def test_tool_result_short_not_truncated():
    """A small tool result (< 40 lines) should not be truncated."""
    small_output = "\n".join(f"file{i}.py" for i in range(5))
    content_blocks = [
        {"type": "tool_result", "tool_use_id": "t1", "content": small_output},
    ]
    lines = [
        json.dumps({"type": "human", "message": {"content": "List"}}),
        json.dumps({"type": "assistant", "message": {"content": content_blocks}}),
    ]
    result = normalize_text("\n".join(lines))
    assert "omitted" not in result
    assert "file4.py" in result


# ---------------------------------------------------------------------------
# normalize_file
# ---------------------------------------------------------------------------


def test_normalize_file(tmp_path: Path):
    content = "\n".join([
        json.dumps({"type": "human", "message": {"content": "What is 2+2?"}}),
        json.dumps({"type": "assistant", "message": {"content": "It's 4."}}),
    ])
    f = tmp_path / "chat.jsonl"
    f.write_text(content, encoding="utf-8")
    result = normalize_file(f)
    assert "> What is 2+2?" in result
    assert "It's 4." in result


def test_normalize_file_plain(tmp_path: Path):
    content = "Hello world"
    f = tmp_path / "notes.txt"
    f.write_text(content, encoding="utf-8")
    result = normalize_file(f)
    assert result == content


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_multi_turn_conversation():
    """Multi-turn: user-assistant-user-assistant interleaved correctly."""
    lines = [
        json.dumps({"type": "human", "message": {"content": "Turn 1 user"}}),
        json.dumps({"type": "assistant", "message": {"content": "Turn 1 assistant"}}),
        json.dumps({"type": "human", "message": {"content": "Turn 2 user"}}),
        json.dumps({"type": "assistant", "message": {"content": "Turn 2 assistant"}}),
    ]
    result = normalize_text("\n".join(lines))
    segments = result.split("\n\n")
    assert len(segments) == 4
    assert segments[0].startswith("> Turn 1 user")
    assert "Turn 1 assistant" in segments[1]
    assert segments[2].startswith("> Turn 2 user")
    assert "Turn 2 assistant" in segments[3]


def test_string_content_extraction():
    """String content (not list of blocks) is handled correctly."""
    lines = [
        json.dumps({"type": "human", "message": {"content": "Simple string content"}}),
        json.dumps({"type": "assistant", "message": {"content": "Simple reply"}}),
    ]
    result = normalize_text("\n".join(lines))
    assert "> Simple string content" in result
    assert "Simple reply" in result
