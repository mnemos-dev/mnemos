"""Auto-refine hook: SessionStart orchestration for last-3 JSONL refinement."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mnemos.pending import PendingState

DEFAULT_LEDGER_SUFFIX = Path(".claude/skills/mnemos-refine-transcripts/state/processed.tsv")
REMINDER_INTERVAL_DAYS = 7
STATUS_FILENAME = ".mnemos-hook-status.json"


def resolve_ledger_path() -> Path:
    """Return the refine-skill ledger path.

    Honors `MNEMOS_REFINE_LEDGER` if set. Otherwise falls back to the canonical
    junction target under the user home directory.
    """
    override = os.environ.get("MNEMOS_REFINE_LEDGER")
    if override:
        return Path(override)
    return Path.home() / DEFAULT_LEDGER_SUFFIX


def _read_ledger_paths(ledger_path: Path) -> set[str]:
    """Return the set of source-JSONL paths recorded in the refine-skill ledger.

    Ledger format is one TSV line per processed JSONL:
    `<source_path>\t<status>\t<note_or_reason>` where status is OK or SKIP.
    Empty or missing file → empty set. Paths are normalised via Path()/str()
    so backslash/slash and case differences between ledger writer and reader
    don't cause spurious re-picks.
    """
    if not ledger_path.exists():
        return set()

    paths: set[str] = set()
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        cols = line.split("\t")
        if not cols or not cols[0].strip():
            continue
        raw = cols[0].strip()
        paths.add(str(Path(raw)))
    return paths


def pick_recent_jsonls(projects_dir: Path, ledger_path: Path, n: int = 3) -> list[Path]:
    """Return up to `n` most-recent (by mtime) JSONLs not already in the ledger."""
    if not projects_dir.exists():
        return []

    ledger_paths = _read_ledger_paths(ledger_path)
    candidates = sorted(
        projects_dir.rglob("*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    picked: list[Path] = []
    for candidate in candidates:
        if str(candidate) in ledger_paths:
            continue
        picked.append(candidate)
        if len(picked) >= n:
            break
    return picked


def compute_backlog(projects_dir: Path, ledger_path: Path) -> int:
    """Count JSONLs under `projects_dir` that are not listed in the ledger.

    Uses the same path normalisation as `pick_recent_jsonls` so counts stay
    consistent between the picker and the backlog reminder.
    """
    if not projects_dir.exists():
        return 0

    ledger_paths = _read_ledger_paths(ledger_path)
    total = 0
    for candidate in projects_dir.rglob("*.jsonl"):
        if str(candidate) not in ledger_paths:
            total += 1
    return total


def should_show_reminder(state: PendingState, today: datetime, backlog: int) -> bool:
    """Decide whether to show the backlog reminder this session.

    Rules:
    - backlog <= 0 → never
    - no `backlog_reminder_last_shown` → yes (first run)
    - otherwise → yes only if ≥ REMINDER_INTERVAL_DAYS since last shown
    """
    if backlog <= 0:
        return False
    if not state.backlog_reminder_last_shown:
        return True
    last = datetime.fromisoformat(state.backlog_reminder_last_shown)
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return today - last >= timedelta(days=REMINDER_INTERVAL_DAYS)


def write_status(
    vault: Path,
    phase: str,
    current: int,
    total: int,
    backlog: int,
    reminder_active: bool,
    started_at: str,
) -> Path:
    """Atomically write the statusline state file (tmp + os.replace)."""
    path = Path(vault) / STATUS_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "phase": phase,
        "current": current,
        "total": total,
        "backlog": backlog,
        "reminder_active": reminder_active,
        "started_at": started_at,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    fd, tmp_name = tempfile.mkstemp(prefix=".mnemos-hook-status.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise

    return path
