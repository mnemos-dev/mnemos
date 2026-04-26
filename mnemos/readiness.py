"""Readiness computation for Identity bootstrap gate + briefing inject gate."""
from __future__ import annotations

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
