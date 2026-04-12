"""Memory Stack — L0-L3 layered recall for Mnemos."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from mnemos.config import MnemosConfig
from mnemos.obsidian import parse_frontmatter


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: 1 token per 4 characters."""
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# MemoryStack
# ---------------------------------------------------------------------------


class MemoryStack:
    """Layered memory recall across L0 (identity), L1 (wings), and L2 (rooms)."""

    def __init__(self, config: MnemosConfig) -> None:
        self.config = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recall(self, level: str = "L1", wing: Optional[str] = None) -> dict:
        """Recall memory at the specified level.

        Args:
            level: One of "L0", "L1", "L2".
            wing:  Wing name — required for L2.

        Returns:
            dict with keys: level, content, token_count
        """
        if level == "L0":
            content = self._load_l0()
        elif level == "L1":
            content = self._load_l1()
        elif level == "L2":
            if wing is None:
                raise ValueError("wing parameter is required for L2 recall")
            content = self._load_l2(wing)
        else:
            raise ValueError(f"Unknown recall level: {level!r}. Use L0, L1, or L2.")

        return {
            "level": level,
            "content": content,
            "token_count": _estimate_tokens(content),
        }

    def wake_up(self) -> dict:
        """Load L0 (identity) + L1 (wings summary) combined.

        Returns:
            dict with keys: identity, wings_summary, token_count
        """
        identity = self._load_l0()
        wings_summary = self._load_l1()
        combined = identity + wings_summary

        return {
            "identity": identity,
            "wings_summary": wings_summary,
            "token_count": _estimate_tokens(combined),
        }

    # ------------------------------------------------------------------
    # Private loaders
    # ------------------------------------------------------------------

    def _load_l0(self) -> str:
        """Read Identity/L0-identity.md and return its body."""
        identity_file = self.config.identity_full_path / "L0-identity.md"
        if not identity_file.exists():
            return ""
        _meta, body = parse_frontmatter(identity_file)
        return body

    def _load_l1(self) -> str:
        """Iterate wings_dir, read each _wing.md, format as '## WingName\\n{body}'."""
        wings_dir = self.config.wings_dir
        if not wings_dir.exists():
            return ""

        parts: list[str] = []
        for wing_dir in sorted(wings_dir.iterdir()):
            if not wing_dir.is_dir():
                continue
            wing_summary = wing_dir / "_wing.md"
            if not wing_summary.exists():
                continue
            _meta, body = parse_frontmatter(wing_summary)
            parts.append(f"## {wing_dir.name}\n{body}")

        return "\n\n".join(parts)

    def _load_l2(self, wing: str) -> str:
        """Iterate room dirs under wing, read each _room.md, format as '### RoomName\\n{body}'."""
        wing_dir = self.config.wings_dir / wing
        if not wing_dir.exists():
            return ""

        parts: list[str] = []
        for room_dir in sorted(wing_dir.iterdir()):
            if not room_dir.is_dir():
                continue
            room_summary = room_dir / "_room.md"
            if not room_summary.exists():
                continue
            _meta, body = parse_frontmatter(room_summary)
            parts.append(f"### {room_dir.name}\n{body}")

        return "\n\n".join(parts)
