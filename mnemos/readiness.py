"""Readiness computation for Identity bootstrap gate + briefing inject gate."""
from __future__ import annotations

import re
from pathlib import Path

from mnemos.auto_refine import _count_user_turns, _is_subagent_jsonl


def count_eligible_jsonls(projects_dir: Path, min_user_turns: int = 3) -> int:
    """Count JSONLs in projects_dir.rglob that pass the noise floor filter."""
    if not projects_dir.exists():
        return 0
    count = 0
    for p in projects_dir.rglob("*.jsonl"):
        if _is_subagent_jsonl(p):
            continue
        if _count_user_turns(p) < min_user_turns:
            continue
        count += 1
    return count


def count_refined_sessions(vault: Path) -> int:
    """Count Sessions/*.md files in the vault."""
    sessions_dir = vault / "Sessions"
    if not sessions_dir.exists():
        return 0
    return sum(1 for _ in sessions_dir.glob("*.md"))


def compute_readiness_pct(refined: int, eligible: int) -> float:
    """Return refined/eligible as percentage. Edge: 0/0 -> 100% (no work pending)."""
    if eligible == 0:
        return 100.0
    return (refined / eligible) * 100.0


def per_cwd_readiness(
    vault: Path,
    cwd: str,
    cwd_slug: str,
    projects_root: Path,
    min_user_turns: int = 3,
) -> dict:
    """Compute readiness for a single cwd.

    Returns: {"refined": int, "eligible": int, "pct": float}
    """
    proj_dir = projects_root / cwd_slug
    eligible = 0
    if proj_dir.exists():
        for p in proj_dir.glob("*.jsonl"):
            if _is_subagent_jsonl(p):
                continue
            if _count_user_turns(p) < min_user_turns:
                continue
            eligible += 1

    refined = 0
    sessions_dir = vault / "Sessions"
    target = cwd.strip().rstrip("/\\")
    if sessions_dir.exists():
        for md in sessions_dir.glob("*.md"):
            try:
                text = md.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
            if not m:
                continue
            for line in m.group(1).splitlines():
                s = line.strip()
                if s.startswith("cwd:"):
                    val = s.split(":", 1)[1].strip().strip("'\"")
                    if val.rstrip("/\\") == target:
                        refined += 1
                    break

    return {
        "refined": refined,
        "eligible": eligible,
        "pct": compute_readiness_pct(refined, eligible),
    }
