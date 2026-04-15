"""Onboarding discovery + classification for `mnemos init`.

Pure functions: scan well-known locations, return a list of
`DiscoveredSource` records. The CLI then drives the interactive flow
(present, ask user, process, update `.mnemos-pending.json`).

3.4a scope: Claude Code JSONL transcripts + vault-internal curated
markdown (Sessions/, memory/, Topics/). Other formats (ChatGPT, Slack,
Claude.ai, Gemini) land in 3.5.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Literal, Optional

# Per-file processing time heuristics (seconds). Used to give the user
# a coarse "this will take ~N min" estimate before they commit.
SECS_PER_CURATED_FILE = 1.5
SECS_PER_RAW_FILE = 7.0

Classification = Literal["curated", "raw"]
SourceKind = Literal["raw-jsonl", "curated-md"]


@dataclass
class DiscoveredSource:
    """A source found during discovery, ready to be presented to the user."""

    id: str
    kind: SourceKind
    root_path: str
    file_count: int
    sample_files: List[str] = field(default_factory=list)

    @property
    def classification(self) -> Classification:
        return classify(self.kind)

    @property
    def estimated_seconds(self) -> float:
        per_file = (
            SECS_PER_RAW_FILE if self.classification == "raw" else SECS_PER_CURATED_FILE
        )
        return self.file_count * per_file


def classify(kind: SourceKind) -> Classification:
    if kind == "raw-jsonl":
        return "raw"
    if kind == "curated-md":
        return "curated"
    raise ValueError(f"unknown source kind: {kind!r}")


def default_claude_projects_dir() -> Optional[Path]:
    """Return the standard `~/.claude/projects` path if it exists, else None.

    Cross-platform via `Path.home()` — works on Windows, macOS, Linux.
    """
    candidate = Path.home() / ".claude" / "projects"
    return candidate if candidate.is_dir() else None


def discover(
    vault_path: str | os.PathLike[str],
    claude_projects_dir: Optional[str | os.PathLike[str]] = None,
    sample_size: int = 3,
) -> List[DiscoveredSource]:
    """Scan known locations and return discovered sources.

    Sources with zero files are omitted. Order is deterministic:
    Claude Code JSONL first, then vault-internal Sessions/memory/Topics.

    Args:
        vault_path: Obsidian vault root.
        claude_projects_dir: Override for `~/.claude/projects`. If None,
            uses `default_claude_projects_dir()`. Pass an explicit path
            from tests to avoid touching the real home directory.
        sample_files: How many file names to capture per source for
            display. Sorted by mtime descending (newest first).
    """
    sources: List[DiscoveredSource] = []
    vault = Path(vault_path)

    # ------- Claude Code transcripts -------
    cc_dir: Optional[Path]
    if claude_projects_dir is not None:
        cand = Path(claude_projects_dir)
        cc_dir = cand if cand.is_dir() else None
    else:
        cc_dir = default_claude_projects_dir()

    if cc_dir is not None:
        jsonls = sorted(cc_dir.rglob("*.jsonl"), key=_mtime_desc)
        if jsonls:
            sources.append(
                DiscoveredSource(
                    id="claude-code-jsonl",
                    kind="raw-jsonl",
                    root_path=str(cc_dir),
                    file_count=len(jsonls),
                    sample_files=[p.name for p in jsonls[:sample_size]],
                )
            )

    # ------- Vault-internal curated markdown -------
    for subdir, source_id in (
        ("Sessions", "vault-sessions"),
        ("memory", "vault-memory"),
        ("Topics", "vault-topics"),
    ):
        path = vault / subdir
        if not path.is_dir():
            continue
        mds = sorted(path.glob("*.md"), key=_mtime_desc)
        if not mds:
            continue
        sources.append(
            DiscoveredSource(
                id=source_id,
                kind="curated-md",
                root_path=str(path),
                file_count=len(mds),
                sample_files=[p.name for p in mds[:sample_size]],
            )
        )

    return sources


def format_estimate(seconds: float) -> str:
    """Render an estimated duration like '~40 dk' or '~12 sn'."""
    if seconds < 60:
        return f"~{int(seconds)} sn"
    if seconds < 3600:
        return f"~{int(round(seconds / 60))} dk"
    return f"~{seconds / 3600:.1f} sa"


def _mtime_desc(p: Path) -> float:
    try:
        return -p.stat().st_mtime
    except OSError:
        return 0.0
