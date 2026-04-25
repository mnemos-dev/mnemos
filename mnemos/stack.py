"""Memory Stack — v1.0: only L0 (Identity Layer).

The drawer paradigm (L1 wings, L2 rooms) was retired in the narrative-first
pivot. ``mnemos_wake_up`` and ``mnemos_recall`` now only surface the
Identity Layer; calls for L1 / L2 receive a deprecation marker.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional


class MemoryStack:
    """Identity Layer reader. L1/L2 deprecated in v1.0 (drawer paradigm gone)."""

    def __init__(self, config) -> None:
        self.config = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def wake_up(self) -> dict:
        """Read ``<vault>/_identity/L0-identity.md`` and return its content."""
        identity_path = Path(self.config.vault_path) / "_identity" / "L0-identity.md"
        if not identity_path.exists():
            return {"identity": "", "token_count": 0}
        content = identity_path.read_text(encoding="utf-8")
        return {
            "identity": content,
            "token_count": max(1, len(content) // 3),  # rough estimate
        }

    def recall(self, level: str = "L0", wing: Optional[str] = None) -> dict:
        """Recall memory at the requested level.

        v1.0: only ``L0`` is supported. ``L1`` and ``L2`` requests return a
        deprecation marker so callers (skills, MCP clients) can detect the
        retirement and migrate.
        """
        if level == "L0":
            return self.wake_up()
        return {
            "deprecated": True,
            "level": level,
            "message": (
                f"Level {level} is deprecated in v1.0; only L0 (Identity) is "
                "supported. The drawer paradigm (wings/rooms) was retired in "
                "the narrative-first pivot."
            ),
        }
