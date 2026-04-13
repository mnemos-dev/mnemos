"""Room Detector — classify a file into one of 13 room categories.

Algorithm:
1. Normalise each path segment (lowercase, hyphens/underscores → stripped variant)
2. Match segments against folder patterns from rooms.yaml (case-insensitive)
3. If a folder match is found, return that room immediately (folder > keywords)
4. Otherwise score the first 3000 chars of text against keyword lists
5. Require 2+ keyword hits to avoid false positives
6. Highest scoring room wins; fallback to "general"
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Load rooms.yaml at module level
# ---------------------------------------------------------------------------

_ROOMS_FILE = Path(__file__).parent / "patterns" / "rooms.yaml"

with _ROOMS_FILE.open(encoding="utf-8") as _f:
    _ROOMS: dict[str, dict[str, list[str]]] = yaml.safe_load(_f)

# Pre-build normalised folder sets for fast lookup
# Normalisation: lowercase, strip hyphens and underscores for comparison
_NORM_FOLDER_MAP: dict[str, str] = {}  # normalised_segment -> room name

for _room, _data in _ROOMS.items():
    for _folder in _data.get("folders", []):
        _norm = re.sub(r"[-_]", "", _folder.lower())
        _NORM_FOLDER_MAP[_norm] = _room


def _normalise(segment: str) -> str:
    """Lowercase and strip hyphens/underscores from a path segment."""
    return re.sub(r"[-_]", "", segment.lower())


def _match_folder(filepath: Path) -> str | None:
    """Return room name if any path segment matches a folder pattern, else None.

    Iterates from deepest directory upward (excluding the file itself).
    First match wins.
    """
    # parts: ('/', 'project', 'frontend', 'App.tsx') — skip root and filename
    parts = filepath.parts
    # Walk directory parts only (exclude final filename)
    for segment in reversed(parts[:-1]):
        norm = _normalise(segment)
        if norm in _NORM_FOLDER_MAP:
            return _NORM_FOLDER_MAP[norm]
    return None


def _score_keywords(text: str) -> str | None:
    """Score first 3000 chars of text against keyword lists.

    Returns the room with the highest score (2+ hits required), or None.
    """
    snippet = text[:3000].lower()
    scores: dict[str, int] = {}

    for room, data in _ROOMS.items():
        keywords = data.get("keywords", [])
        count = sum(1 for kw in keywords if kw.lower() in snippet)
        if count >= 2:
            scores[room] = count

    if not scores:
        return None

    return max(scores, key=lambda r: scores[r])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_room(filepath: Path, text: str) -> str:
    """Detect the room category for a file.

    Parameters
    ----------
    filepath:
        Path to the file being classified.
    text:
        Text content of the file (may be empty string).

    Returns
    -------
    str
        One of the 13 room names or "general" as fallback.
    """
    # 1. Folder-path matching takes priority
    room = _match_folder(filepath)
    if room:
        return room

    # 2. Keyword scoring on first 3000 chars
    if text:
        room = _score_keywords(text)
        if room:
            return room

    return "general"
