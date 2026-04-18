"""Palace — Wing/Room/Hall structure management with recycle."""
from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path
from typing import List, Optional

from mnemos.config import MnemosConfig
from mnemos.obsidian import write_drawer_file, parse_drawer_file


# TR character -> ASCII equivalent for fuzzy matching. Preserves
# semantic identity across spelling variants ("Satın Alma" vs "satin-alma").
_TR_NORMALIZE = str.maketrans({
    'ı': 'i', 'İ': 'i', 'I': 'i',
    'ş': 's', 'Ş': 's',
    'ü': 'u', 'Ü': 'u',
    'ğ': 'g', 'Ğ': 'g',
    'ç': 'c', 'Ç': 'c',
    'ö': 'o', 'Ö': 'o',
})


def _normalize_for_match(name: str) -> str:
    """Normalize a name for case-insensitive, diacritic-insensitive, delimiter-insensitive match.

    Used by Palace.canonical_wing to unify "Satın Alma", "satin-alma",
    "SATIN_ALMA" as the same wing identity. Distinct names like
    "Satın Alma Otomasyonu" still normalize differently.
    """
    if not name:
        return ""
    collapsed = name.translate(_TR_NORMALIZE).lower()
    return re.sub(r"[-_ ]+", "", collapsed)


def _sanitize_name(name: str) -> str:
    """Sanitize a wing/room name for use as a directory name.

    Removes characters invalid on Windows (: * ? \" < > |) and
    replaces spaces with hyphens.
    """
    # Remove Windows-invalid chars
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    # Replace spaces and multiple hyphens
    name = name.strip().replace(' ', '-')
    name = re.sub(r'-+', '-', name)
    # Truncate to reasonable length
    return name[:60] or "unnamed"


class Palace:
    """Manages the Wing/Room/Hall directory structure inside a Mnemos vault."""

    def __init__(self, config: MnemosConfig) -> None:
        self.config = config

    # ------------------------------------------------------------------
    # Structure management
    # ------------------------------------------------------------------

    def ensure_structure(self) -> None:
        """Create Wings/, Identity/, and _recycled/ directories if absent."""
        self.config.wings_dir.mkdir(parents=True, exist_ok=True)
        self.config.identity_full_path.mkdir(parents=True, exist_ok=True)
        self.config.recycled_full_path.mkdir(parents=True, exist_ok=True)

    def canonical_wing(self, name: str) -> str:
        """Resolve *name* to an existing wing's canonical casing if one exists.

        Matching is diacritic- and delimiter-insensitive via
        :func:`_normalize_for_match`, so "Satın Alma" / "satin-alma" /
        "SATIN_ALMA" all resolve to the first-created directory.
        Distinct names (different token sequences) remain distinct wings.
        """
        sanitized = _sanitize_name(name)
        if self.config.wings_dir.exists():
            target_norm = _normalize_for_match(sanitized)
            for p in self.config.wings_dir.iterdir():
                if p.is_dir() and _normalize_for_match(p.name) == target_norm:
                    return p.name
        return sanitized

    def create_wing(self, name: str) -> Path:
        """Create a wing directory (no summary file yet — summary is lazy).

        The _wing.md summary is written on first drawer via :meth:`add_drawer`
        so that empty wings don't persist after a failed mine.
        """
        name = self.canonical_wing(name)
        wing_dir = self.config.wings_dir / name
        wing_dir.mkdir(parents=True, exist_ok=True)
        return wing_dir

    def create_room(self, wing: str, room: str) -> Path:
        """Create a room directory (no summary, no hall subdirs — all lazy).

        Auto-creates the parent wing if it does not exist. Hall directories
        and the _room.md summary are created on first drawer via
        :meth:`add_drawer`.
        """
        wing = self.canonical_wing(wing)
        room = _sanitize_name(room)
        wing_dir = self.config.wings_dir / wing
        if not wing_dir.exists():
            self.create_wing(wing)

        room_dir = wing_dir / room
        room_dir.mkdir(parents=True, exist_ok=True)
        return room_dir

    # ------------------------------------------------------------------
    # Drawer management
    # ------------------------------------------------------------------

    def add_drawer(
        self,
        wing: str,
        room: str,
        hall: str,
        text: str,
        source: str,
        importance: int,
        entities: list,
        language: str,
    ) -> Path:
        """Create a drawer .md file in the correct hall directory.

        Auto-creates wing and room if they do not exist. Generates a unique
        filename with a date prefix.

        Args:
            wing: Wing name.
            room: Room name.
            hall: Hall name (one of config.halls).
            text: Body text of the drawer.
            source: Source reference string.
            importance: Importance score.
            entities: List of entity strings.
            language: Language code (e.g. "en", "tr").

        Returns:
            Path to the created drawer file.
        """
        # Sanitize names for filesystem safety; resolve wing case-insensitively
        wing = self.canonical_wing(wing)
        room = _sanitize_name(room)
        hall = _sanitize_name(hall)

        # Ensure wing + room (and hall subdir) exist
        room_dir = self.config.wings_dir / wing / room
        if not room_dir.exists():
            self.create_room(wing, room)

        hall_dir = room_dir / hall
        hall_dir.mkdir(parents=True, exist_ok=True)

        # Lazy summaries: write _wing.md / _room.md on first drawer
        wing_summary = self.config.wings_dir / wing / "_wing.md"
        if not wing_summary.exists():
            write_drawer_file(
                wing_summary,
                metadata={
                    "wing": wing,
                    "created": date.today().isoformat(),
                    "type": "wing-summary",
                },
                body=f"# {wing}\n\nWing summary for {wing}.",
            )

        room_summary = room_dir / "_room.md"
        if not room_summary.exists():
            write_drawer_file(
                room_summary,
                metadata={
                    "wing": wing,
                    "room": room,
                    "created": date.today().isoformat(),
                    "type": "room-summary",
                },
                body=f"# {room}\n\nRoom summary for {room} inside wing {wing}.",
            )

        # Build a unique filename: <source_date>-<slug>.md
        source_path = Path(source)
        source_date = _extract_source_date(source_path) if source_path.exists() \
            else date.today().isoformat()
        filename = _unique_filename(hall_dir, source_date=source_date, slug_text=text)

        filepath = hall_dir / filename

        write_drawer_file(
            filepath,
            metadata={
                "wing": wing,
                "room": room,
                "hall": hall,
                "source": source,
                "importance": importance,
                "entities": entities,
                "language": language,
            },
            body=text,
        )

        return filepath

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def list_wings(self) -> List[str]:
        """Return all wing directory names inside Wings/."""
        if not self.config.wings_dir.exists():
            return []
        return [
            p.name
            for p in self.config.wings_dir.iterdir()
            if p.is_dir()
        ]

    def list_drawers(
        self,
        wing: Optional[str] = None,
        room: Optional[str] = None,
    ) -> List[Path]:
        """List all drawer .md files, excluding _wing.md and _room.md.

        Args:
            wing: If given, restrict to this wing.
            room: If given (requires wing), restrict to this room.

        Returns:
            Sorted list of drawer file Paths.
        """
        if wing is not None:
            search_root = self.config.wings_dir / wing
            if room is not None:
                search_root = search_root / room
        else:
            search_root = self.config.wings_dir

        if not search_root.exists():
            return []

        drawers: List[Path] = []
        for md_file in search_root.rglob("*.md"):
            if md_file.name.startswith("_"):
                continue
            drawers.append(md_file)

        return sorted(drawers)

    # ------------------------------------------------------------------
    # Recycle
    # ------------------------------------------------------------------

    def recycle_drawer(self, drawer_path: Path) -> Path:
        """Move a drawer to _recycled/ with a date prefix.

        Handles name collisions by appending a numeric suffix.

        Args:
            drawer_path: Absolute path to the drawer file to recycle.

        Returns:
            Path to the recycled file inside _recycled/.
        """
        self.config.recycled_full_path.mkdir(parents=True, exist_ok=True)

        today = date.today().isoformat()
        base_name = drawer_path.name

        # Build destination with date prefix (avoid duplication if already prefixed)
        if base_name.startswith(today):
            candidate_name = base_name
        else:
            candidate_name = f"{today}-{base_name}"

        dest = _unique_dest(self.config.recycled_full_path, candidate_name)
        shutil.move(str(drawer_path), str(dest))
        return dest


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

_DATE_PREFIX_RE = re.compile(r"^\s*(\d{4}-\d{2}-\d{2})\s*[-—:–]?\s*")


def _extract_source_date(filepath: Path) -> str:
    """Return an ISO-8601 date string derived from a source file.

    Resolution order:
      1. Leading YYYY-MM-DD in the filename stem.
      2. Frontmatter ``date`` or ``created`` field.
      3. File mtime (local date).
    """
    stem = filepath.stem
    m = _DATE_PREFIX_RE.match(stem)
    if m:
        return m.group(1)

    # Try frontmatter — cheap parse of leading --- block
    try:
        with filepath.open("r", encoding="utf-8") as fh:
            first = fh.readline().strip()
            if first == "---":
                buf = []
                for line in fh:
                    if line.strip() == "---":
                        break
                    buf.append(line)
                fm_yaml = "".join(buf)
                import yaml as _yaml
                fm = _yaml.safe_load(fm_yaml) or {}
                for key in ("date", "created"):
                    value = fm.get(key)
                    if value:
                        text = str(value)[:10]
                        if _DATE_PREFIX_RE.match(text + "-"):
                            return text
    except Exception:
        pass

    # mtime fallback
    try:
        ts = filepath.stat().st_mtime
        return date.fromtimestamp(ts).isoformat()
    except OSError:
        return date.today().isoformat()


def _slugify(text: str, max_len: int = 40) -> str:
    """Convert text to a safe filename slug.

    Strips leading YYYY-MM-DD prefix (common in refined session titles
    like "2026-04-13 — Phase 0 Foundation") so drawer filenames do not
    end up with two dates. Truncates at word boundaries.
    """
    text = _DATE_PREFIX_RE.sub("", text)
    slug = text.lower()
    slug = "".join(c if c.isalnum() or c in (" ", "-") else "" for c in slug)
    slug = slug.strip().replace(" ", "-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    slug = slug.strip("-")
    if not slug:
        return "drawer"
    if len(slug) <= max_len:
        return slug
    truncated = slug[:max_len]
    last_hyphen = truncated.rfind("-")
    if last_hyphen > max_len // 2:
        truncated = truncated[:last_hyphen]
    return truncated.rstrip("-")


def _unique_filename(directory: Path, source_date: str, slug_text: str) -> str:
    """Return a unique ``<source_date>-<slug>.md`` filename inside *directory*."""
    slug = _slugify(slug_text)
    candidate = f"{source_date}-{slug}.md"
    if not (directory / candidate).exists():
        return candidate
    counter = 1
    while True:
        candidate = f"{source_date}-{slug}-{counter}.md"
        if not (directory / candidate).exists():
            return candidate
        counter += 1


def _unique_dest(directory: Path, filename: str) -> Path:
    """Return a unique destination path inside *directory* for *filename*."""
    dest = directory / filename
    if not dest.exists():
        return dest

    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 1
    while True:
        dest = directory / f"{stem}-{counter}{suffix}"
        if not dest.exists():
            return dest
        counter += 1
