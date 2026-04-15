"""Pending sources state — `.mnemos-pending.json` at vault root.

Tracks resumable onboarding/import batches so a crashed `mnemos init` or
`mnemos import` does not start over. Each source is one entry keyed by id.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal, Optional

SCHEMA_VERSION = 1
PENDING_FILENAME = ".mnemos-pending.json"

SourceStatus = Literal["pending", "in-progress", "done", "skipped-by-user", "error"]
VALID_STATUSES: tuple[SourceStatus, ...] = (
    "pending",
    "in-progress",
    "done",
    "skipped-by-user",
    "error",
)


@dataclass
class PendingSource:
    """One discovered source awaiting (or in the middle of) processing."""

    id: str
    path: str
    kind: str
    status: SourceStatus = "pending"
    discovered_at: str = ""
    total: int = 0
    processed: int = 0
    last_action: str = ""

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(
                f"invalid status {self.status!r}; expected one of {VALID_STATUSES}"
            )
        if not self.discovered_at:
            self.discovered_at = _utc_now_iso()


@dataclass
class PendingState:
    """Whole `.mnemos-pending.json` document."""

    version: int = SCHEMA_VERSION
    sources: List[PendingSource] = field(default_factory=list)

    def get(self, source_id: str) -> Optional[PendingSource]:
        for src in self.sources:
            if src.id == source_id:
                return src
        return None


def pending_path(vault_path: str | os.PathLike[str]) -> Path:
    return Path(vault_path) / PENDING_FILENAME


def load(vault_path: str | os.PathLike[str]) -> PendingState:
    """Read `.mnemos-pending.json`. Returns empty state if file is missing."""
    path = pending_path(vault_path)
    if not path.exists():
        return PendingState()

    raw = json.loads(path.read_text(encoding="utf-8"))
    version = raw.get("version", SCHEMA_VERSION)
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported pending schema version {version}; this build expects {SCHEMA_VERSION}"
        )

    sources = [PendingSource(**entry) for entry in raw.get("sources", [])]
    return PendingState(version=version, sources=sources)


def save(vault_path: str | os.PathLike[str], state: PendingState) -> Path:
    """Atomically write `.mnemos-pending.json` (tmp file + os.replace)."""
    path = pending_path(vault_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": state.version,
        "sources": [asdict(src) for src in state.sources],
    }

    fd, tmp_name = tempfile.mkstemp(
        prefix=".mnemos-pending.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise

    return path


def upsert_source(
    vault_path: str | os.PathLike[str],
    source: PendingSource,
) -> PendingState:
    """Insert source if new; otherwise replace the entry with matching id."""
    state = load(vault_path)
    for i, existing in enumerate(state.sources):
        if existing.id == source.id:
            state.sources[i] = source
            break
    else:
        state.sources.append(source)
    save(vault_path, state)
    return state


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
