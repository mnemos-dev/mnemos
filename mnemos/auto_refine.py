"""Auto-refine hook: SessionStart orchestration for last-3 JSONL refinement."""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_LEDGER_SUFFIX = Path(".claude/skills/mnemos-refine-transcripts/state/processed.tsv")


def resolve_ledger_path() -> Path:
    """Return the refine-skill ledger path.

    Honors `MNEMOS_REFINE_LEDGER` if set. Otherwise falls back to the canonical
    junction target under the user home directory.
    """
    override = os.environ.get("MNEMOS_REFINE_LEDGER")
    if override:
        return Path(override)
    return Path.home() / DEFAULT_LEDGER_SUFFIX
