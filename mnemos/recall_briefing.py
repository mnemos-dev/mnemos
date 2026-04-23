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


# ---------------------------------------------------------------------------
# Mode yaml inline read (mirror of auto_refine._read_mine_mode)
# ---------------------------------------------------------------------------

def read_recall_mode(vault: Path) -> str:
    """Return recall_mode from <vault>/mnemos.yaml (default: "script")."""
    yaml_path = vault / "mnemos.yaml"
    if not yaml_path.exists():
        return "script"
    try:
        text = yaml_path.read_text(encoding="utf-8")
    except OSError:
        return "script"
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("recall_mode:"):
            return s.split(":", 1)[1].strip().strip("'\"")
    return "script"


# ---------------------------------------------------------------------------
# Cache file (<vault>/.mnemos-briefings/<slug>.md)
# ---------------------------------------------------------------------------

def cache_path_for(vault: Path, cwd_slug: str) -> Path:
    return vault / CACHE_DIR / f"{cwd_slug}.md"


def read_cache_body(cache_path: Path) -> str:
    """Return cache body (frontmatter stripped). Empty string if missing/corrupt."""
    if not cache_path.exists():
        return ""
    try:
        text = cache_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    m = re.match(r"^---\r?\n.*?\r?\n---\r?\n", text, re.DOTALL)
    if m:
        return text[m.end():].lstrip("\n")
    return text


def write_cache(
    cache_path: Path,
    body: str,
    cwd: str,
    session_count: int,
    drawer_count: int,
    generated_at: str | None = None,
) -> None:
    """Write cache file with frontmatter + body. Creates parent dir if needed."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if generated_at is None:
        from datetime import datetime
        generated_at = datetime.now().isoformat(timespec="seconds")
    front = (
        f"---\n"
        f"cwd: {cwd}\n"
        f"generated_at: {generated_at}\n"
        f"session_count_used: {session_count}\n"
        f"drawer_count_used: {drawer_count}\n"
        f"---\n\n"
    )
    cache_path.write_text(front + body.lstrip("\n"), encoding="utf-8")


# ---------------------------------------------------------------------------
# Session frontmatter counter for staleness check
# ---------------------------------------------------------------------------

def count_refined_sessions_for_cwd(vault: Path, cwd: str) -> int:
    """Count Sessions/*.md files whose frontmatter cwd matches exactly.

    Case-sensitive, trailing whitespace/slash on both sides trimmed before
    compare. Sessions without cwd frontmatter are excluded.
    """
    target = cwd.strip().rstrip("/\\")
    sessions_dir = vault / "Sessions"
    if not sessions_dir.exists():
        return 0
    count = 0
    for md in sessions_dir.glob("*.md"):
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
        if not m:
            continue
        front = m.group(1)
        for line in front.splitlines():
            s = line.strip()
            if s.startswith("cwd:"):
                val = s.split(":", 1)[1].strip().strip("'\"")
                if val.rstrip("/\\") == target:
                    count += 1
                break
    return count


# ---------------------------------------------------------------------------
# Refine ledger + unrefined JSONL discovery
# ---------------------------------------------------------------------------

DEFAULT_REFINE_LEDGER = Path.home() / ".claude/skills/mnemos-refine-transcripts/state/processed.tsv"
DEFAULT_CLAUDE_PROJECTS = Path.home() / ".claude/projects"


def load_refine_ledger_jsonls(ledger: Path) -> set[str]:
    """Return set of JSONL abs paths with OK status in the refine ledger.

    Ledger format: <jsonl>\\t<status>\\t<session_md> (3 cols, tab-separated).
    """
    out: set[str] = set()
    if not ledger.exists():
        return out
    try:
        with ledger.open("r", encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                parts = raw.rstrip("\r\n").split("\t")
                if len(parts) < 3:
                    continue
                if parts[1] == "OK":
                    out.add(parts[0])
    except OSError:
        pass
    return out


def find_unrefined_jsonls_for_cwd(
    cwd_slug: str,
    projects_root: Path,
    ledger: Path,
) -> list[Path]:
    """List .jsonl files in ~/.claude/projects/<slug>/ NOT in refine ledger.

    Sorted by mtime (oldest first). The caller should also skip any JSONL
    whose PID marker indicates a live session.
    """
    proj_dir = projects_root / cwd_slug
    if not proj_dir.exists():
        return []
    processed = load_refine_ledger_jsonls(ledger)
    candidates: list[Path] = []
    for jsonl in proj_dir.glob("*.jsonl"):
        if str(jsonl) not in processed:
            candidates.append(jsonl)
    return sorted(candidates, key=lambda p: p.stat().st_mtime)
