"""install-end-hook CLI tests — atomic install, idempotent, --uninstall, roundtrip."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from mnemos.cli import cmd_install_end_hook


def test_install_end_hook_adds_entry_atomically(tmp_path, monkeypatch):
    settings = tmp_path / "settings.json"
    settings.write_text(
        '{"permissions":{"allow":["Read"]},'
        '"hooks":{"SessionStart":[{"matcher":"*","_managed_by":"mnemos-auto-refine",'
        '"_version":"v1.0","hooks":[]}]}}',
        encoding="utf-8",
    )
    monkeypatch.setattr("mnemos.cli._user_settings_path", lambda: settings)
    args = argparse.Namespace(
        vault="C:/test/vault", uninstall=False, v1=True
    )
    rc = cmd_install_end_hook(args)
    assert rc == 0

    data = json.loads(settings.read_text(encoding="utf-8"))
    # Pre-existing SessionStart entry preserved.
    assert any(
        e.get("_managed_by") == "mnemos-auto-refine"
        for e in data["hooks"]["SessionStart"]
    )
    # SessionEnd entry added with v1.1 signature.
    assert "SessionEnd" in data["hooks"]
    se_entries = data["hooks"]["SessionEnd"]
    assert any(
        e.get("_managed_by") == "mnemos-session-end" and e.get("_version") == "v1.1"
        for e in se_entries
    )
    # Backup file created alongside the live settings file.
    assert any(
        p.name.startswith("settings.json.bak-") for p in tmp_path.iterdir()
    )


def test_install_end_hook_idempotent(tmp_path, monkeypatch):
    """Re-running install must not duplicate the entry."""
    settings = tmp_path / "settings.json"
    settings.write_text('{"hooks":{}}', encoding="utf-8")
    monkeypatch.setattr("mnemos.cli._user_settings_path", lambda: settings)
    args = argparse.Namespace(vault="C:/v", uninstall=False, v1=True)
    cmd_install_end_hook(args)
    cmd_install_end_hook(args)
    data = json.loads(settings.read_text(encoding="utf-8"))
    se = data["hooks"]["SessionEnd"]
    managed = [e for e in se if e.get("_managed_by") == "mnemos-session-end"]
    assert len(managed) == 1


def test_install_end_hook_uninstall_removes_only_managed(tmp_path, monkeypatch):
    settings = tmp_path / "settings.json"
    settings.write_text(
        '{"hooks":{"SessionEnd":['
        '{"_managed_by":"mnemos-session-end","_version":"v1.1","hooks":[]},'
        '{"_managed_by":"other-tool","hooks":[]}'
        ']}}',
        encoding="utf-8",
    )
    monkeypatch.setattr("mnemos.cli._user_settings_path", lambda: settings)
    args = argparse.Namespace(vault="", uninstall=True, v1=False)
    rc = cmd_install_end_hook(args)
    assert rc == 0
    data = json.loads(settings.read_text(encoding="utf-8"))
    se = data["hooks"]["SessionEnd"]
    assert all(e.get("_managed_by") != "mnemos-session-end" for e in se)
    assert any(e.get("_managed_by") == "other-tool" for e in se)


def test_install_then_uninstall_roundtrip_preserves_other_settings(tmp_path, monkeypatch):
    """install + uninstall must leave non-managed settings untouched."""
    settings = tmp_path / "settings.json"
    original = {
        "permissions": {"allow": ["Bash(npm *)"]},
        "statusLine": {"type": "command", "command": "echo hi"},
        "hooks": {
            "SessionStart": [
                {
                    "_managed_by": "mnemos-auto-refine",
                    "_version": "v1.0",
                    "hooks": [{"type": "command", "command": "x", "timeout": 1000}],
                }
            ]
        },
    }
    settings.write_text(json.dumps(original, indent=2), encoding="utf-8")
    monkeypatch.setattr("mnemos.cli._user_settings_path", lambda: settings)

    cmd_install_end_hook(
        argparse.Namespace(vault="C:/v", uninstall=False, v1=True)
    )
    cmd_install_end_hook(
        argparse.Namespace(vault="", uninstall=True, v1=False)
    )

    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["permissions"] == original["permissions"]
    assert data["statusLine"] == original["statusLine"]
    assert data["hooks"]["SessionStart"] == original["hooks"]["SessionStart"]
    assert "SessionEnd" not in data.get("hooks", {})
