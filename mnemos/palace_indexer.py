"""Palace indexer — walk an existing palace root and index drawers into
the vector backend without re-running classification.

Use-case: after ``mnemos pilot --accept skill`` promotes a skill-mined
palace to ``Mnemos/``, the vector index still reflects the recycled
script-mined palace. This module does a frontmatter-authoritative
re-index: reads drawer .md files, trusts their frontmatter (wing, room,
hall, entities), and writes (id, text, metadata) tuples directly to
``backend.index_drawers_bulk``.

No mining pipeline. No regex. No chunking (drawer body is already the
fragment). See docs/specs/2026-04-19-phase1-ai-boost-design.md §4.2.2
step 5 (``--from-palace`` motivation).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from mnemos.obsidian import parse_frontmatter
from mnemos.search import SearchBackend


@dataclass
class IndexStats:
    palace_root: Path
    indexed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    dropped_first: bool = False


def walk_palace(palace_root: Path) -> Iterator[Path]:
    """Yield drawer .md files under ``<palace_root>/wings/**/``.

    Skips ``_wing.md``, ``_room.md``, and any file whose name starts with
    ``_`` (lazy summary files, mnemos convention).
    """
    wings = Path(palace_root) / "wings"
    if not wings.exists() or not wings.is_dir():
        return
    for md in wings.rglob("*.md"):
        if md.name.startswith("_"):
            continue
        if not md.is_file():
            continue
        yield md


def parse_drawer(path: Path) -> tuple[str, str, dict] | None:
    """Read a drawer .md file and produce a (drawer_id, text, metadata)
    tuple suitable for :meth:`SearchBackend.index_drawer`.

    Returns None if the file is missing required frontmatter fields
    (``wing``, ``room``, ``hall``) — caller should treat as skipped.
    """
    try:
        meta, body = parse_frontmatter(path)
    except OSError:
        return None

    wing = meta.get("wing")
    room = meta.get("room")
    hall = meta.get("hall")
    if not wing or not room or not hall:
        return None

    drawer_id = path.stem
    source = meta.get("source") or ""
    language = meta.get("language") or "en"

    metadata = {
        "wing": str(wing),
        "room": str(room),
        "hall": str(hall),
        "source": str(source),
        "source_path": str(source),
        "language": str(language),
    }
    importance = meta.get("importance")
    if importance is not None:
        try:
            metadata["importance"] = float(importance)
        except (TypeError, ValueError):
            pass

    return drawer_id, body.strip() or str(wing), metadata


def index_palace(
    backend: SearchBackend,
    palace_root: Path,
    drop_first: bool = True,
) -> IndexStats:
    """Drop and re-index the mined collection from drawer files in
    ``palace_root``. Returns an :class:`IndexStats` summary.

    When ``drop_first`` is True (default) both the mined and raw
    collections are wiped via :meth:`SearchBackend.drop_and_reinit` so
    stale entries from a prior palace don't linger. The raw collection
    is left empty by this indexer — it must be repopulated separately by
    the standard miner scanning ``Sessions/`` / ``Topics/``. Callers who
    need a populated raw collection should invoke the normal
    ``mnemos mine`` pipeline after this.
    """
    stats = IndexStats(palace_root=Path(palace_root))

    if drop_first:
        backend.drop_and_reinit()
        stats.dropped_first = True

    batch: list[tuple[str, str, dict]] = []
    for drawer_path in walk_palace(palace_root):
        parsed = parse_drawer(drawer_path)
        if parsed is None:
            stats.skipped += 1
            stats.errors.append(f"skipped (bad frontmatter): {drawer_path.name}")
            continue
        batch.append(parsed)

    if batch:
        backend.index_drawers_bulk(batch)
        stats.indexed = len(batch)

    return stats
