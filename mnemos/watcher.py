"""Mnemos vault file watcher — detects changes to .md files via watchdog."""
from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Callable, Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from mnemos.config import MnemosConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EVENT_CREATED = "created"
EVENT_MODIFIED = "modified"
EVENT_DELETED = "deleted"
EVENT_MOVED = "moved"

# (event_type, filepath, dest_path)
ChangeCallback = Callable[[str, Path, Optional[Path]], None]


# ---------------------------------------------------------------------------
# Internal event handler
# ---------------------------------------------------------------------------


class _VaultEventHandler(FileSystemEventHandler):
    """Watchdog handler that delegates filesystem events to VaultWatcher."""

    def __init__(self, watcher: "VaultWatcher") -> None:
        super().__init__()
        self._watcher = watcher

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._handle_event(EVENT_CREATED, Path(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._handle_event(EVENT_MODIFIED, Path(event.src_path))

    def on_deleted(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._handle_event(EVENT_DELETED, Path(event.src_path))

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._handle_event(
                EVENT_MOVED, Path(event.src_path), Path(event.dest_path)
            )


# ---------------------------------------------------------------------------
# VaultWatcher
# ---------------------------------------------------------------------------


class VaultWatcher:
    """Watches a vault directory for .md file changes."""

    def __init__(self, config: MnemosConfig, on_change: ChangeCallback) -> None:
        self._config = config
        self._on_change = on_change
        self._observer: Optional[Observer] = None

    # ------------------------------------------------------------------
    # Ignore logic
    # ------------------------------------------------------------------

    def should_ignore(self, filepath: Path) -> bool:
        """Return True if filepath should be ignored.

        Conditions:
        - Not a .md file → ignore
        - Relative path matches any pattern in config.watcher_ignore:
          - Patterns ending with "/" → directory prefix match
          - Other patterns → fnmatch against filename and rel_path string
        """
        # Must be a .md file
        if filepath.suffix.lower() != ".md":
            return True

        vault = Path(self._config.vault_path)
        try:
            rel_path = filepath.relative_to(vault)
        except ValueError:
            # Outside vault — ignore
            return True

        # Normalise to forward slashes for cross-platform consistency
        rel_str = rel_path.as_posix()
        filename = filepath.name

        for pattern in self._config.watcher_ignore:
            if pattern.endswith("/"):
                # Directory pattern — check if rel_path starts with the prefix
                dir_prefix = pattern  # e.g. ".obsidian/"
                if rel_str.startswith(dir_prefix):
                    return True
            else:
                # Glob pattern — match against filename and full rel path
                if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(rel_str, pattern):
                    return True

        return False

    # ------------------------------------------------------------------
    # Cold-start: detect changed files
    # ------------------------------------------------------------------

    def detect_changed_files(self, mine_log: dict[str, float]) -> list[Path]:
        """Walk vault, return .md files modified after their mine_log timestamp.

        Args:
            mine_log: Mapping of absolute path string → processed timestamp (float).

        Returns:
            List of Path objects for files that need (re)processing.
        """
        changed: list[Path] = []
        vault = Path(self._config.vault_path)

        for root, _dirs, files in os.walk(vault):
            for fname in files:
                filepath = Path(root) / fname
                if self.should_ignore(filepath):
                    continue
                mtime = filepath.stat().st_mtime
                last_processed = mine_log.get(str(filepath))
                if last_processed is None or mtime > last_processed:
                    changed.append(filepath)

        return changed

    # ------------------------------------------------------------------
    # Observer lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the watchdog observer as a daemon thread."""
        handler = _VaultEventHandler(self)
        observer = Observer()
        observer.schedule(handler, str(self._config.vault_path), recursive=True)
        observer.daemon = True
        observer.start()
        self._observer = observer

    def stop(self) -> None:
        """Stop and join the watchdog observer."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None

    # ------------------------------------------------------------------
    # Internal event dispatch
    # ------------------------------------------------------------------

    def _handle_event(
        self,
        event_type: str,
        filepath: Path,
        dest_path: Optional[Path] = None,
    ) -> None:
        """Check ignore rules, then invoke the on_change callback."""
        # For moved events, check both src and dest; ignore if src matches
        if self.should_ignore(filepath):
            return
        self._on_change(event_type, filepath, dest_path)
