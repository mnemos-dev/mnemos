"""Cwd-aware SessionStart auto-briefing hook wrapper.

Called by Claude Code's SessionStart hook when `recall_mode: skill`. Decides
between fast-path (inject existing briefing + bg regen) and blocking catch-up
(sync refine + mine + brief for this cwd's unrefined JSONLs) based on a
per-cwd state file (.mnemos-cwd-state.json).

See docs/specs/2026-04-23-v0.4-task-4.3-first-ship-design.md for the full
decision tree.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any


STATE_FILENAME = ".mnemos-cwd-state.json"
CACHE_DIR = ".mnemos-briefings"
STATE_LOCK = STATE_FILENAME + ".flock"
CATCH_UP_LOCK = ".mnemos-catch-up.flock"
STALE_THRESHOLD = 3  # session-count diff that triggers sync regen in SUB-B1


# ---------------------------------------------------------------------------
# Cwd slug normalization
# ---------------------------------------------------------------------------

def cwd_to_slug(cwd: str) -> str:
    """Convert a cwd path to the Claude-Code-style slug used in project dirs.

    Rules:
      - Strip leading/trailing whitespace and trailing path separators
      - Replace any non-\\w-hyphen char with "-"
      - Collapse repeated dashes
      - Preserve underscores and letters (including Unicode word chars)
    """
    s = cwd.strip().rstrip("/\\")
    s = re.sub(r"[^\w-]", "-", s, flags=re.UNICODE)
    s = re.sub(r"-{2,}", "--", s)  # cap at double-dash (original pattern)
    return s


# ---------------------------------------------------------------------------
# State file
# ---------------------------------------------------------------------------

@dataclass
class CwdState:
    version: int = 1
    cwds: Dict[str, Dict[str, Any]] = field(default_factory=dict)


def load_state(vault: Path) -> CwdState:
    """Load cwd-state.json; return empty state if missing or corrupt."""
    path = vault / STATE_FILENAME
    if not path.exists():
        return CwdState()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return CwdState()
    if not isinstance(raw, dict):
        return CwdState()
    return CwdState(
        version=int(raw.get("version", 1)),
        cwds=dict(raw.get("cwds", {})),
    )


def save_state(vault: Path, state: CwdState) -> None:
    """Atomic write of state JSON (write-then-rename)."""
    path = vault / STATE_FILENAME
    tmp_path = vault / (STATE_FILENAME + ".tmp")
    data = {"version": state.version, "cwds": state.cwds}
    tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, path)
