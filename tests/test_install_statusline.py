"""Tests for `mnemos install-statusline` — idempotent statusline snippet installer."""
from __future__ import annotations

import json
import os
from pathlib import Path


def _home(tmp_path: Path, monkeypatch) -> Path:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    monkeypatch.setattr("pathlib.Path.home", lambda: home)
    return home


def _is_windows() -> bool:
    return os.name == "nt"


def test_install_fresh_no_existing_statusline(tmp_path, monkeypatch):
    """No prior statusline → create ~/.claude/mnemos-statusline.{sh,cmd} and set settings.json."""
    from mnemos.install_statusline import install_statusline

    home = _home(tmp_path, monkeypatch)
    result = install_statusline(vault=tmp_path, uninstall=False)

    assert result.status == "installed"
    # Script file was created
    assert result.script_path is not None
    assert Path(result.script_path).exists()
    # settings.json exists and points to our script
    settings = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert "statusLine" in settings
    assert settings["statusLine"]["type"] == "command"
    assert str(Path(result.script_path)).replace("\\", "/") in settings["statusLine"]["command"].replace("\\", "/")


def test_install_fresh_script_contains_snippet_marker(tmp_path, monkeypatch):
    """Fresh install: the created script must contain the managed-by marker for later detection."""
    from mnemos.install_statusline import install_statusline, STATUSLINE_MARKER

    _home(tmp_path, monkeypatch)
    result = install_statusline(vault=tmp_path, uninstall=False)
    body = Path(result.script_path).read_text(encoding="utf-8")
    assert STATUSLINE_MARKER in body


def test_install_idempotent(tmp_path, monkeypatch):
    """Re-running install on an already-installed system reports already-installed and does not duplicate."""
    from mnemos.install_statusline import install_statusline

    _home(tmp_path, monkeypatch)
    install_statusline(vault=tmp_path, uninstall=False)
    result2 = install_statusline(vault=tmp_path, uninstall=False)
    assert result2.status == "already-installed"

    # Script must not have two copies of the snippet. Each installed block
    # contains the marker twice (begin + end fence), so one block = 2.
    body = Path(result2.script_path).read_text(encoding="utf-8")
    from mnemos.install_statusline import STATUSLINE_MARKER
    assert body.count(STATUSLINE_MARKER) == 2


def test_install_appends_to_existing_bash_script(tmp_path, monkeypatch):
    """If settings.json already points to a user-owned bash script, append the snippet to it."""
    if _is_windows():
        # Bash path specific — skip on Windows runners.
        import pytest
        pytest.skip("bash-path case")
    from mnemos.install_statusline import install_statusline, STATUSLINE_MARKER

    home = _home(tmp_path, monkeypatch)
    user_script = home / ".claude" / "statusline.sh"
    user_script.write_text("#!/usr/bin/env bash\necho hello\n", encoding="utf-8")
    (home / ".claude" / "settings.json").write_text(
        json.dumps({"statusLine": {"type": "command", "command": f"bash {user_script}"}}),
        encoding="utf-8",
    )

    result = install_statusline(vault=tmp_path, uninstall=False)
    assert result.status == "installed"
    body = user_script.read_text(encoding="utf-8")
    assert "echo hello" in body  # user content preserved
    assert STATUSLINE_MARKER in body
    assert "MNEMOS_VAULT" in body


def test_install_appends_to_existing_cmd_script(tmp_path, monkeypatch):
    """If settings.json points to a .cmd script, append with rem-style marker."""
    if not _is_windows():
        import pytest
        pytest.skip("windows-cmd case")
    from mnemos.install_statusline import install_statusline, STATUSLINE_MARKER

    home = _home(tmp_path, monkeypatch)
    user_script = home / ".claude" / "statusline.cmd"
    user_script.write_text("@echo off\necho hello\n", encoding="utf-8")
    (home / ".claude" / "settings.json").write_text(
        json.dumps({"statusLine": {"type": "command", "command": str(user_script)}}),
        encoding="utf-8",
    )

    result = install_statusline(vault=tmp_path, uninstall=False)
    assert result.status == "installed"
    body = user_script.read_text(encoding="utf-8")
    assert "echo hello" in body
    assert STATUSLINE_MARKER in body
    assert "MNEMOS_VAULT" in body


def test_install_preserves_other_settings(tmp_path, monkeypatch):
    """Installing must not clobber unrelated settings keys."""
    from mnemos.install_statusline import install_statusline

    home = _home(tmp_path, monkeypatch)
    (home / ".claude" / "settings.json").write_text(
        json.dumps({"theme": "dark", "hooks": {"Stop": [{"matcher": "", "hooks": []}]}}),
        encoding="utf-8",
    )
    install_statusline(vault=tmp_path, uninstall=False)
    settings = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert settings["theme"] == "dark"
    assert "Stop" in settings["hooks"]
    assert "statusLine" in settings


def test_install_creates_backup(tmp_path, monkeypatch):
    """Existing settings.json must be backed up before modification (only on install, not uninstall-of-nothing)."""
    from mnemos.install_statusline import install_statusline

    home = _home(tmp_path, monkeypatch)
    settings_path = home / ".claude" / "settings.json"
    settings_path.write_text(json.dumps({"theme": "light"}), encoding="utf-8")

    result = install_statusline(vault=tmp_path, uninstall=False)
    assert result.settings_backup_path is not None
    assert Path(result.settings_backup_path).exists()
    assert json.loads(Path(result.settings_backup_path).read_text(encoding="utf-8")) == {"theme": "light"}


def test_uninstall_fresh_install_removes_script_and_settings(tmp_path, monkeypatch):
    """After a fresh install, uninstall should remove both the script and the statusLine key."""
    from mnemos.install_statusline import install_statusline

    home = _home(tmp_path, monkeypatch)
    install_result = install_statusline(vault=tmp_path, uninstall=False)
    script_path = Path(install_result.script_path)

    result = install_statusline(vault=tmp_path, uninstall=True)
    assert result.status == "uninstalled"
    assert not script_path.exists()
    settings = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert "statusLine" not in settings


def test_uninstall_from_existing_script_keeps_user_content(tmp_path, monkeypatch):
    """Uninstall from a user-owned script must only remove our snippet block, leaving the rest intact."""
    if _is_windows():
        import pytest
        pytest.skip("bash-path case")
    from mnemos.install_statusline import install_statusline, STATUSLINE_MARKER

    home = _home(tmp_path, monkeypatch)
    user_script = home / ".claude" / "statusline.sh"
    user_script.write_text("#!/usr/bin/env bash\necho hello\n", encoding="utf-8")
    (home / ".claude" / "settings.json").write_text(
        json.dumps({"statusLine": {"type": "command", "command": f"bash {user_script}"}}),
        encoding="utf-8",
    )

    install_statusline(vault=tmp_path, uninstall=False)
    result = install_statusline(vault=tmp_path, uninstall=True)
    assert result.status == "uninstalled"
    body = user_script.read_text(encoding="utf-8")
    assert "echo hello" in body  # user content preserved
    assert STATUSLINE_MARKER not in body
    # settings.json statusLine must still point to the user's script (we didn't own it)
    settings = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert "statusLine" in settings


def test_uninstall_when_nothing_installed(tmp_path, monkeypatch):
    """Uninstall on a clean system reports not-found without erroring."""
    from mnemos.install_statusline import install_statusline

    _home(tmp_path, monkeypatch)
    result = install_statusline(vault=tmp_path, uninstall=True)
    assert result.status == "not-found"
