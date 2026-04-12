"""Tests for mnemos.watcher — vault change detection."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from mnemos.config import MnemosConfig
from mnemos.watcher import VaultWatcher


# ---------------------------------------------------------------------------
# Test 1: should_ignore — directory and glob patterns
# ---------------------------------------------------------------------------


def test_should_ignore(config: MnemosConfig, tmp_vault: Path) -> None:
    """Ignored paths return True; valid vault notes return False."""
    watcher = VaultWatcher(config, on_change=lambda *a: None)

    # These should be ignored
    assert watcher.should_ignore(tmp_vault / ".obsidian" / "workspace.json") is True
    assert watcher.should_ignore(tmp_vault / "Mnemos" / "_recycled" / "old.md") is True
    assert watcher.should_ignore(tmp_vault / "Templates" / "Daily.md") is True
    assert watcher.should_ignore(tmp_vault / "board.canvas") is True

    # These should NOT be ignored
    assert watcher.should_ignore(tmp_vault / "Sessions" / "2026-04-10.md") is False
    assert watcher.should_ignore(tmp_vault / "Mnemos" / "wings" / "decisions.md") is False


# ---------------------------------------------------------------------------
# Test 2: should_ignore — non-.md files are always ignored
# ---------------------------------------------------------------------------


def test_should_ignore_non_md(config: MnemosConfig, tmp_vault: Path) -> None:
    """Non-.md files are always ignored; .md files pass the extension check."""
    watcher = VaultWatcher(config, on_change=lambda *a: None)

    assert watcher.should_ignore(tmp_vault / "Sessions" / "image.png") is True
    assert watcher.should_ignore(tmp_vault / "Topics" / "data.json") is True
    assert watcher.should_ignore(tmp_vault / "Sessions" / "note.md") is False


# ---------------------------------------------------------------------------
# Test 3: detect_changed_files
# ---------------------------------------------------------------------------


def test_detect_changed_files(config: MnemosConfig, tmp_vault: Path) -> None:
    """Only files newer than their mine_log timestamp are returned."""
    watcher = VaultWatcher(config, on_change=lambda *a: None)

    # Create two .md files
    old_note = tmp_vault / "Sessions" / "old.md"
    new_note = tmp_vault / "Sessions" / "new.md"

    old_note.write_text("old content", encoding="utf-8")
    new_note.write_text("new content", encoding="utf-8")

    # Simulate mine_log: old_note already processed (future timestamp), new_note not
    far_future = time.time() + 9999
    mine_log = {str(old_note): far_future}

    changed = watcher.detect_changed_files(mine_log)

    assert new_note in changed
    assert old_note not in changed
