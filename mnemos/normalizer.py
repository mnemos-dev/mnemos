"""Conversation Normalizer — convert 5 chat export formats to standard transcript.

Public API:
    normalize_file(filepath)  → str
    normalize_text(text)      → str
    detect_format(text)       → 'claude_code_jsonl' | 'chatgpt_json' | 'slack_json' | 'plain_text'

Output format:
    > user message here
    assistant response here

    > next user message
    assistant response
"""
from __future__ import annotations

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TOOL_TRUNCATE_LINES = 20  # keep first N + last N lines of tool results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalize_file(filepath: Path) -> str:
    """Read file, detect format, normalize to transcript."""
    text = Path(filepath).read_text(encoding="utf-8")
    return normalize_text(text)


def normalize_text(text: str) -> str:
    """Detect format and normalize to standard transcript."""
    fmt = detect_format(text)
    if fmt == "claude_code_jsonl":
        return _normalize_claude_code_jsonl(text)
    if fmt == "chatgpt_json":
        return _normalize_chatgpt_json(text)
    if fmt == "slack_json":
        return _normalize_slack_json(text)
    # plain_text — passthrough
    return text


def detect_format(text: str) -> str:
    """Return format identifier for *text*.

    Returns one of:
        'claude_code_jsonl' | 'chatgpt_json' | 'slack_json' | 'plain_text'
    """
    stripped = text.strip()
    if not stripped:
        return "plain_text"

    # Try JSON array first (Slack)
    if stripped.startswith("["):
        try:
            data = json.loads(stripped)
            if isinstance(data, list) and data and isinstance(data[0], dict) and data[0].get("type") == "message":
                return "slack_json"
        except json.JSONDecodeError:
            pass

    # Try single JSON object (ChatGPT)
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            if isinstance(data, dict) and "mapping" in data:
                return "chatgpt_json"
        except json.JSONDecodeError:
            pass

    # Try JSONL (Claude Code) — each non-empty line is a JSON object with "type"
    lines = [l for l in stripped.splitlines() if l.strip()]
    if lines:
        parsed = []
        for line in lines:
            try:
                obj = json.loads(line)
                if isinstance(obj, dict) and "type" in obj:
                    parsed.append(obj)
                else:
                    break
            except json.JSONDecodeError:
                break
        if len(parsed) == len(lines) and parsed:
            return "claude_code_jsonl"

    return "plain_text"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _truncate_tool_output(text: str) -> str:
    """Truncate long tool output: keep first 20 + last 20 lines."""
    lines = text.splitlines()
    n = len(lines)
    limit = _TOOL_TRUNCATE_LINES
    if n <= limit * 2:
        return text
    kept_head = lines[:limit]
    kept_tail = lines[n - limit:]
    skipped = n - limit * 2
    return "\n".join(kept_head) + f"\n... [{skipped} lines omitted] ...\n" + "\n".join(kept_tail)


def _extract_content(content) -> list[dict]:
    """Normalise content to a list of typed blocks.

    Accepts:
        str            → [{"type": "text", "text": str}]
        list of blocks → as-is
        dict           → [dict]
    """
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return content
    if isinstance(content, dict):
        return [content]
    return []


def _blocks_to_text(blocks: list[dict]) -> str:
    """Convert a list of content blocks to a single string."""
    parts: list[str] = []
    for block in blocks:
        btype = block.get("type", "")
        if btype == "text":
            parts.append(block.get("text", ""))
        elif btype == "tool_use":
            name = block.get("name", "tool")
            inp = block.get("input", {})
            # Format tool call compactly
            if isinstance(inp, dict):
                args = ", ".join(f"{k}={repr(v)}" for k, v in list(inp.items())[:3])
            else:
                args = str(inp)
            parts.append(f"[{name}({args})]")
        elif btype == "tool_result":
            raw = block.get("content", "")
            if isinstance(raw, list):
                raw = "\n".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in raw)
            elif not isinstance(raw, str):
                raw = str(raw)
            truncated = _truncate_tool_output(raw)
            parts.append(f"[tool_result]\n{truncated}")
        else:
            # Unknown block — try generic text extraction
            text = block.get("text") or block.get("content") or str(block)
            parts.append(str(text))
    return "\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Format normalisers
# ---------------------------------------------------------------------------


def _normalize_claude_code_jsonl(text: str) -> str:
    """Normalize Claude Code JSONL format."""
    lines = [l for l in text.strip().splitlines() if l.strip()]
    objects = [json.loads(l) for l in lines]

    # Build (role, text) pairs
    pairs: list[tuple[str, str]] = []
    for obj in objects:
        role = obj.get("type", "")  # "human" or "assistant"
        message = obj.get("message", {})
        content = message.get("content", "") if isinstance(message, dict) else ""
        blocks = _extract_content(content)
        text_body = _blocks_to_text(blocks)

        if role == "human":
            pairs.append(("user", text_body))
        elif role == "assistant":
            pairs.append(("assistant", text_body))

    return _render_pairs(_merge_consecutive_assistant(pairs))


def _normalize_chatgpt_json(text: str) -> str:
    """Normalize ChatGPT JSON export format."""
    data = json.loads(text)
    mapping: dict = data.get("mapping", {})

    # Find root node (no parent or parent is None)
    root_id = None
    for node_id, node in mapping.items():
        if node.get("parent") is None:
            root_id = node_id
            break

    if root_id is None:
        return ""

    # Walk the tree in order: follow children links
    ordered: list[dict] = []
    visited: set[str] = set()

    def _walk(node_id: str) -> None:
        if node_id in visited or node_id not in mapping:
            return
        visited.add(node_id)
        node = mapping[node_id]
        ordered.append(node)
        for child_id in node.get("children", []):
            _walk(child_id)

    _walk(root_id)

    pairs: list[tuple[str, str]] = []
    for node in ordered:
        msg = node.get("message")
        if not msg:
            continue
        author = msg.get("author", {})
        role = author.get("role", "")
        if role not in ("user", "assistant"):
            continue
        content_obj = msg.get("content", {})
        # ChatGPT content: {"parts": ["text", ...]} or string
        if isinstance(content_obj, dict):
            parts = content_obj.get("parts", [])
            text_body = "\n".join(str(p) for p in parts if p)
        elif isinstance(content_obj, str):
            text_body = content_obj
        else:
            text_body = str(content_obj)

        if text_body.strip():
            pairs.append((role, text_body))

    return _render_pairs(_merge_consecutive_assistant(pairs))


def _normalize_slack_json(text: str) -> str:
    """Normalize Slack JSON export format.

    Convention: first unique user → 'user', others → 'assistant'.
    """
    data: list[dict] = json.loads(text)
    messages = [m for m in data if isinstance(m, dict) and m.get("type") == "message"]

    if not messages:
        return ""

    first_user = messages[0].get("user") or messages[0].get("username") or ""
    pairs: list[tuple[str, str]] = []
    for msg in messages:
        uid = msg.get("user") or msg.get("username") or ""
        text_body = msg.get("text", "")
        if not text_body.strip():
            continue
        role = "user" if uid == first_user else "assistant"
        pairs.append((role, text_body))

    return _render_pairs(_merge_consecutive_assistant(pairs))


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------


def _merge_consecutive_assistant(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Merge consecutive assistant messages into one."""
    if not pairs:
        return pairs
    merged: list[tuple[str, str]] = []
    for role, text in pairs:
        if merged and merged[-1][0] == "assistant" and role == "assistant":
            prev_role, prev_text = merged[-1]
            merged[-1] = (prev_role, prev_text + "\n" + text)
        else:
            merged.append((role, text))
    return merged


def _render_pairs(pairs: list[tuple[str, str]]) -> str:
    """Render (role, text) pairs to standard transcript format."""
    segments: list[str] = []
    for role, text in pairs:
        if role == "user":
            segments.append(f"> {text}")
        else:
            segments.append(text)
    return "\n\n".join(segments)
