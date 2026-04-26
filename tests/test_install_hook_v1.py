"""Tests for v1.0 install-hook atomic + idempotent behavior."""
from __future__ import annotations

import json
from pathlib import Path


def test_install_hook_v1_writes_atomic(monkeypatch, tmp_path):
    """install-hook --v1 writes settings.json in single atomic op, replacing v0.x."""
    from mnemos.cli import _install_hook_v1

    settings_path = tmp_path / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(json.dumps({
        "hooks": {
            "SessionStart": [
                {"_managed_by": "mnemos-auto-refine", "_version": "v0.x", "hooks": []},
                {"_managed_by": "other-tool", "hooks": []},
            ]
        }
    }))
    monkeypatch.setattr("mnemos.cli._user_settings_path", lambda: settings_path)

    _install_hook_v1(vault=tmp_path / "vault")

    data = json.loads(settings_path.read_text())
    entries = data["hooks"]["SessionStart"]
    auto_refine = [e for e in entries if e.get("_managed_by") == "mnemos-auto-refine"]
    assert len(auto_refine) == 1
    assert auto_refine[0]["_version"] == "v1.0"
    other = [e for e in entries if e.get("_managed_by") == "other-tool"]
    assert len(other) == 1  # untouched


def test_install_hook_v1_idempotent(monkeypatch, tmp_path):
    """Running install-hook --v1 twice yields same state."""
    from mnemos.cli import _install_hook_v1

    settings_path = tmp_path / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text('{"hooks": {"SessionStart": []}}')
    monkeypatch.setattr("mnemos.cli._user_settings_path", lambda: settings_path)

    _install_hook_v1(vault=tmp_path / "vault")
    first = settings_path.read_text()
    _install_hook_v1(vault=tmp_path / "vault")
    second = settings_path.read_text()
    assert first == second


def test_auto_refine_hook_graceful_fail_on_stale_v0_entry(monkeypatch, capsys, tmp_path):
    """When v1.0 binary is invoked from a v0.x hook entry, emit guidance and exit 0."""
    from mnemos.auto_refine_hook import main

    settings_path = tmp_path / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(json.dumps({
        "hooks": {
            "SessionStart": [
                {"_managed_by": "mnemos-auto-refine", "_version": "v0.x"},
            ]
        }
    }))
    monkeypatch.setattr("mnemos.auto_refine_hook._user_settings_path", lambda: settings_path)

    exit_code = main(argv=["fake-vault"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "install-hook --v1" in captured.err


def test_recall_briefing_graceful_fail_on_stale_v0_entry(monkeypatch, capsys, tmp_path):
    from mnemos.recall_briefing import main

    settings_path = tmp_path / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(json.dumps({
        "hooks": {
            "SessionStart": [
                {"_managed_by": "mnemos-recall-briefing", "_version": "v0.x"},
            ]
        }
    }))
    monkeypatch.setattr("mnemos.recall_briefing._user_settings_path", lambda: settings_path)

    exit_code = main(argv=["fake-vault"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "install-hook --v1" in captured.err
