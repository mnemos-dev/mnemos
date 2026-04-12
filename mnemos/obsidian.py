"""Obsidian I/O — frontmatter parsing and drawer file management."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_frontmatter(filepath: Path) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter and body from a Markdown file.

    Returns:
        (metadata_dict, body_text)
        If no frontmatter is present, returns ({}, full_text).
        Malformed YAML is handled gracefully — returns ({}, full_text).
    """
    text = filepath.read_text(encoding="utf-8")

    # Must start with '---' on its own line
    if not text.startswith("---"):
        return {}, text

    # Find the closing '---'
    # Skip the opening marker and search for the next one
    rest = text[3:]
    # Allow optional newline immediately after opening ---
    if rest.startswith("\n"):
        rest = rest[1:]
    elif rest.startswith("\r\n"):
        rest = rest[2:]

    # Find closing marker
    close_pos = _find_closing_marker(rest)
    if close_pos == -1:
        # No closing marker — treat as plain file
        return {}, text

    yaml_block = rest[:close_pos]
    after_marker = rest[close_pos + 3:]  # skip '---'

    # Strip a single leading newline from body
    if after_marker.startswith("\r\n"):
        after_marker = after_marker[2:]
    elif after_marker.startswith("\n"):
        after_marker = after_marker[1:]

    try:
        meta: dict[str, Any] = yaml.safe_load(yaml_block) or {}
        if not isinstance(meta, dict):
            meta = {}
    except yaml.YAMLError:
        meta = {}

    return meta, after_marker


def write_drawer_file(
    filepath: Path,
    metadata: dict[str, Any],
    body: str,
) -> None:
    """Write a Markdown file with YAML frontmatter.

    - Creates parent directories automatically.
    - Injects ``mined_at`` timestamp (UTC ISO-8601) if not already present.
    - Output format::

        ---
        <yaml>
        ---

        <body>
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Inject mined_at if absent
    meta = dict(metadata)
    if "mined_at" not in meta:
        meta["mined_at"] = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    yaml_block = yaml.dump(
        meta,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=True,
    ).rstrip("\n")

    content = f"---\n{yaml_block}\n---\n\n{body}\n"
    filepath.write_text(content, encoding="utf-8")


def parse_drawer_file(filepath: Path) -> dict[str, Any]:
    """Parse a drawer file into a structured dict.

    Returns a dict with keys:
        wing, room, hall, text, source, importance,
        entities, language, mined_at, filepath
    Missing frontmatter keys default to None (or [] for list fields).
    """
    meta, body = parse_frontmatter(filepath)

    return {
        "wing": meta.get("wing"),
        "room": meta.get("room"),
        "hall": meta.get("hall"),
        "text": body,
        "source": meta.get("source"),
        "importance": meta.get("importance"),
        "entities": meta.get("entities") or [],
        "language": meta.get("language"),
        "mined_at": meta.get("mined_at"),
        "filepath": filepath,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_closing_marker(text: str) -> int:
    """Return the index of the closing '---' marker in *text*, or -1.

    We look for '---' that appears at the start of a line (after a newline).
    """
    # Check line by line to avoid matching '---' inside YAML values
    pos = 0
    for line in text.splitlines(keepends=True):
        if line.rstrip("\r\n") == "---":
            return pos
        pos += len(line)
    return -1
