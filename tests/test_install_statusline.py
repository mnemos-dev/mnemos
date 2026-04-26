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


# ---------------------------------------------------------------------------
# v0.3.0a fix — packaged snippet path (must work for pip-install users too)
# ---------------------------------------------------------------------------


def test_snippet_path_resolves_inside_mnemos_package():
    """The snippet source-of-truth must live inside the `mnemos` package so
    it ships in the wheel. Pre-3.10a this lived at `<repo>/scripts/`, which
    was excluded from the wheel — pip-installed users got a broken block."""
    from pathlib import Path
    from mnemos.install_statusline import _repo_snippet_path

    p = _repo_snippet_path()
    assert p.exists(), f"packaged snippet must exist at install time, got {p}"
    # Must be reachable from the mnemos package directory.
    import mnemos
    pkg_dir = Path(mnemos.__file__).resolve().parent
    assert pkg_dir in p.resolve().parents, \
        f"snippet must live inside the mnemos package; got {p} (pkg={pkg_dir})"


def test_install_fresh_block_references_packaged_snippet(tmp_path, monkeypatch):
    """The block written into the user's statusline script must reference the
    packaged snippet path, not the old `<repo>/scripts/` path."""
    from mnemos.install_statusline import install_statusline

    _home(tmp_path, monkeypatch)
    result = install_statusline(vault=tmp_path, uninstall=False)
    body = Path(result.script_path).read_text(encoding="utf-8")
    # Must NOT reference the legacy scripts/ path; must reference _resources/.
    assert "/scripts/statusline_snippet" not in body.replace("\\", "/"), \
        f"block still references legacy <repo>/scripts/; got:\n{body}"
    assert "_resources/statusline_snippet" in body.replace("\\", "/"), \
        f"block must reference mnemos/_resources/; got:\n{body}"


# ---------------------------------------------------------------------------
# v1.0 statusline format — drop mining, add identity refresh marker
# ---------------------------------------------------------------------------


def test_statusline_snippet_includes_identity_field():
    """The v1.0 statusline must surface the identity-refresh timestamp so
    users see when their L0 identity layer was last regenerated."""
    snippet_path = Path(__file__).parent.parent / "mnemos" / "_resources" / "statusline_snippet.sh"
    content = snippet_path.read_text(encoding="utf-8")
    assert "identity_last_refreshed" in content


def test_statusline_snippet_does_not_reference_mining():
    """v1.0 dropped mining entirely — the statusline must not mention it."""
    snippet_path = Path(__file__).parent.parent / "mnemos" / "_resources" / "statusline_snippet.sh"
    content = snippet_path.read_text(encoding="utf-8")
    assert "mine" not in content.lower()
    assert "mining" not in content.lower()


def test_install_appends_to_existing_msys_path_on_windows(tmp_path, monkeypatch):
    """Settings.json on Windows often stores the statusline command as
    `bash /c/Users/.../foo.sh` (Git Bash POSIX style). The installer must
    recognize that path so it appends to the user's existing script
    instead of falling through to fresh mode (which would replace the
    user's custom statusline with a minimal mnemos-only one)."""
    if not _is_windows():
        import pytest
        pytest.skip("MSYS path semantics are Windows-only")
    from mnemos.install_statusline import install_statusline, STATUSLINE_MARKER

    home = _home(tmp_path, monkeypatch)
    user_script = home / ".claude" / "statusline.sh"
    user_script.write_text("#!/usr/bin/env bash\necho hello\n", encoding="utf-8")

    # Simulate Git Bash POSIX path. tmp_path is e.g. C:\Users\...\T\pytest-of-...\test_x0
    # MSYS form: /c/Users/.../T/pytest-of-.../test_x0/home/.claude/statusline.sh
    win_path = str(user_script)
    drive = win_path[0].lower()
    rest = win_path[2:].replace("\\", "/")
    msys_path = f"/{drive}{rest}"

    (home / ".claude" / "settings.json").write_text(
        json.dumps({"statusLine": {"type": "command", "command": f"bash {msys_path}"}}),
        encoding="utf-8",
    )

    result = install_statusline(vault=tmp_path, uninstall=False)
    assert result.status == "installed"
    assert not result.owned, \
        "should be append-mode, not fresh-mode (user already has a statusline script)"
    body = user_script.read_text(encoding="utf-8")
    assert "echo hello" in body  # user content preserved
    assert STATUSLINE_MARKER in body
    # Target is a .sh script — block must use bash syntax, NOT cmd syntax.
    # (Pre-fix this picked syntax from os.name and produced `rem`/`set`/`call`
    # for a bash target on Windows.)
    assert "source " in body, f"bash-target block must use `source`; got:\n{body}"
    assert "export MNEMOS_VAULT" in body
    assert "rem ---" not in body
    assert "call \"" not in body
    # And it must point at the .sh snippet, not the .cmd one.
    assert "statusline_snippet.sh" in body
    assert "statusline_snippet.cmd" not in body
