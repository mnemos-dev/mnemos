"""Tests for top-level :func:`mnemos.cli.main` dispatch.

Issue C1 (post Task 4 review): Sentinel argparse subparsers for v1.0-removed
commands (``mine``, ``pilot``, ``migrate``, ``catch-up``, ``import claude-code``)
relied on ``argparse.REMAINDER`` to slurp arguments before routing to
``cmd_removed``. Empirically REMAINDER does not capture ``--``-prefixed flags
(Python issue #17050), so ``mnemos mine --rebuild`` produced an unfriendly
``error: unrecognized arguments: --rebuild`` instead of the migration nudge.

The fix pre-dispatches these legacy commands at the top of :func:`main` BEFORE
``parse_args``. These regressions lock that behavior down.

Issue C2: ``cmd_init`` inlined ``Palace.ensure_structure`` after the v1.0
mining strip but dropped the ``_recycled/`` mkdir. CLAUDE.md documents
``_recycled/`` as the canonical soft-delete target, so the directory must
exist after ``mnemos init``.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


# ---------------------------------------------------------------------------
# C1 — legacy command pre-dispatch
# ---------------------------------------------------------------------------


def test_cli_mine_with_flags_prints_removal_message(capsys):
    """`mnemos mine --rebuild` should print friendly removal, not argparse error."""
    from mnemos.cli import main

    rc = main(["mine", "--rebuild"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "removed in v1.0" in captured.err.lower()
    assert "legacy/atomic-paradigm" in captured.err


def test_cli_pilot_with_subcmd_prints_removal_message(capsys):
    """`mnemos pilot --accept skill` should print friendly removal, not argparse error."""
    from mnemos.cli import main

    rc = main(["pilot", "--accept", "skill"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "removed in v1.0" in captured.err.lower()


def test_cli_import_claude_code_with_flags_prints_removal_message(capsys):
    """`mnemos import claude-code --projects-dir /x` points users to the refine skill."""
    from mnemos.cli import main

    rc = main(["import", "claude-code", "--projects-dir", "/x"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "/mnemos-refine-transcripts" in captured.err


def test_cli_bare_mine_prints_removal_message(capsys):
    """Bare `mnemos mine` (no flags) should also print the friendly removal message."""
    from mnemos.cli import main

    rc = main(["mine"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "removed in v1.0" in captured.err.lower()


# ---------------------------------------------------------------------------
# C2 — cmd_init creates _recycled/
# ---------------------------------------------------------------------------


def test_cmd_init_creates_recycled_directory(tmp_path, monkeypatch):
    """v1.0: `mnemos init` should create _recycled/ for the soft-delete convention."""
    from types import SimpleNamespace

    from mnemos.cli import cmd_init

    vault = tmp_path / "vault"
    vault.mkdir()  # pre-create so cmd_init skips the "create dir? [y/N]" prompt
    args = SimpleNamespace(vault=str(vault))

    # Force `discover()` to return no sources so the onboarding phase short-
    # circuits without prompting per-source — keeps the canned-input list small
    # and stable regardless of the test machine's ~/.claude/projects state.
    monkeypatch.setattr("mnemos.onboarding.discover", lambda *_a, **_k: [])

    # Drive the interactive wizard with canned inputs:
    #   1. languages → "en"
    #   2. enable LLM → "n"
    #   3. backend choice → "" (default ChromaDB)
    #   4. install hook → "n"
    #   5. install statusline → "n"
    #   6. install recall hook → "n"
    inputs = iter(["en", "n", "", "n", "n", "n"])
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: next(inputs))

    cmd_init(args)

    # Canonical structural assertions
    assert (vault / "Mnemos").is_dir(), "palace_dir must exist"
    assert (vault / "Sessions").is_dir(), "Sessions/ must exist"
    assert (vault / "Mnemos" / "_recycled").is_dir(), (
        "_recycled/ must exist — CLAUDE.md soft-delete convention"
    )
