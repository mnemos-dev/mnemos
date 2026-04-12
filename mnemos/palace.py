"""Palace — Wing/Room/Hall structure management with recycle."""
from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path
from typing import List, Optional

from mnemos.config import MnemosConfig
from mnemos.obsidian import write_drawer_file, parse_drawer_file


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

    def create_wing(self, name: str) -> Path:
        """Create a wing directory and its _wing.md summary file.

        Args:
            name: Wing name (used as directory name).

        Returns:
            Path to the wing directory.
        """
        wing_dir = self.config.wings_dir / name
        wing_dir.mkdir(parents=True, exist_ok=True)

        summary_file = wing_dir / "_wing.md"
        if not summary_file.exists():
            write_drawer_file(
                summary_file,
                metadata={
                    "wing": name,
                    "created": date.today().isoformat(),
                    "type": "wing-summary",
                },
                body=f"# {name}\n\nWing summary for {name}.",
            )

        return wing_dir

    def create_room(self, wing: str, room: str) -> Path:
        """Create a room directory, _room.md, and one subdir per configured hall.

        Auto-creates the parent wing if it does not exist.

        Args:
            wing: Wing name.
            room: Room name (used as directory name).

        Returns:
            Path to the room directory.
        """
        # Ensure wing exists
        wing_dir = self.config.wings_dir / wing
        if not wing_dir.exists():
            self.create_wing(wing)

        room_dir = wing_dir / room
        room_dir.mkdir(parents=True, exist_ok=True)

        # Write _room.md summary
        summary_file = room_dir / "_room.md"
        if not summary_file.exists():
            write_drawer_file(
                summary_file,
                metadata={
                    "wing": wing,
                    "room": room,
                    "created": date.today().isoformat(),
                    "type": "room-summary",
                },
                body=f"# {room}\n\nRoom summary for {room} inside wing {wing}.",
            )

        # Create one subdir per configured hall
        for hall in self.config.halls:
            (room_dir / hall).mkdir(exist_ok=True)

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
        # Ensure wing + room (and hall subdir) exist
        room_dir = self.config.wings_dir / wing / room
        if not room_dir.exists():
            self.create_room(wing, room)

        hall_dir = room_dir / hall
        hall_dir.mkdir(parents=True, exist_ok=True)

        # Build a unique filename: <date>-<slug>-<counter>.md
        today = date.today().isoformat()
        slug = _slugify(text)
        filename = _unique_filename(hall_dir, today, slug)

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


def _slugify(text: str, max_len: int = 40) -> str:
    """Convert text to a safe filename slug."""
    slug = text.lower()
    # Keep only alphanumerics, spaces, hyphens
    slug = "".join(c if c.isalnum() or c in (" ", "-") else "" for c in slug)
    slug = slug.strip().replace(" ", "-")
    # Collapse repeated hyphens
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug[:max_len].strip("-") or "drawer"


def _unique_filename(directory: Path, date_prefix: str, slug: str) -> str:
    """Return a unique filename in *directory* with the given date prefix and slug."""
    candidate = f"{date_prefix}-{slug}.md"
    if not (directory / candidate).exists():
        return candidate

    counter = 1
    while True:
        candidate = f"{date_prefix}-{slug}-{counter}.md"
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
