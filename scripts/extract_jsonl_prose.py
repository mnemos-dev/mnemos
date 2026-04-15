"""Condense a Claude Code JSONL transcript into a compact prose digest.

Drops: hooks, progress, thinking blocks, tool_use payloads, tool_result bodies,
sidechain/subagent chatter, file-history snapshots.
Keeps: user messages, assistant top-level text content.

Output is a plain ``>`` quoted chat flow so an LLM refiner can reason about
the conversation without swallowing tool spam.

Usage:
    python scripts/extract_jsonl_prose.py <path.jsonl>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def extract(jsonl_path: Path, max_chars_per_turn: int = 4000) -> str:
    lines: list[str] = []
    first_ts: str | None = None
    turn_count = 0
    with jsonl_path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if obj.get("isSidechain"):
                continue

            ts = obj.get("timestamp")
            ev_type = obj.get("type")

            # User turns
            if ev_type == "user":
                msg = obj.get("message", {})
                content = msg.get("content")
                text = _stringify_user_content(content)
                if not text:
                    continue
                if first_ts is None and ts:
                    first_ts = ts
                turn_count += 1
                lines.append(f"> USER [{(ts or '')[:19]}]")
                lines.append(_truncate(text, max_chars_per_turn))
                lines.append("")

            # Assistant top-level text (skip thinking + tool_use)
            elif ev_type == "assistant":
                msg = obj.get("message", {})
                content = msg.get("content", [])
                if isinstance(content, list):
                    texts = [
                        c.get("text", "") for c in content
                        if isinstance(c, dict) and c.get("type") == "text"
                    ]
                    joined = "\n".join(t for t in texts if t).strip()
                    if not joined:
                        continue
                    if first_ts is None and ts:
                        first_ts = ts
                    lines.append(f"> ASSISTANT [{(ts or '')[:19]}]")
                    lines.append(_truncate(joined, max_chars_per_turn))
                    lines.append("")

            # Ignore: progress, hook_progress, file-history-snapshot, tool_use,
            # tool_result, system, summary, etc.

    header = [
        f"# Transcript digest: {jsonl_path.name}",
        f"Source: {jsonl_path}",
        f"First timestamp: {first_ts or '(unknown)'}",
        f"User turns detected: {turn_count}",
        "",
    ]
    return "\n".join(header + lines)


def _stringify_user_content(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
                # Skip tool_result blocks (tool output noise)
        return "\n".join(p for p in parts if p).strip()
    return ""


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n…[truncated, {len(text) - limit} more chars]"


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: extract_jsonl_prose.py <path.jsonl>", file=sys.stderr)
        sys.exit(2)
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"not a file: {path}", file=sys.stderr)
        sys.exit(1)
    print(extract(path))


if __name__ == "__main__":
    main()
