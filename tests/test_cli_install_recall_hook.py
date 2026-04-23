"""Tests for mnemos install-recall-hook CLI."""
from __future__ import annotations

import json
from pathlib import Path

from mnemos.recall_briefing import (
    install_recall_hook,
    RECALL_HOOK_TIMEOUT_MS,
    RECALL_HOOK_MARKER,
    _is_recall_entry,
)


def _recall_matches(entries: list[dict]) -> list[dict]:
    return [e for e in entries if _is_recall_entry(e)]


def test_install_recall_hook_adds_session_start_entry(tmp_path: Path, monkeypatch) -> None:
    settings = tmp_path / "settings.json"
    monkeypatch.setattr("mnemos.recall_briefing.SETTINGS_PATH", settings)

    # Pre-seed with existing auto-refine hook (real Claude Code schema:
    # grouped entry with matcher + _managed_by + nested hooks list)
    settings.write_text(json.dumps({
        "hooks": {
            "SessionStart": [{
                "matcher": "",
                "_managed_by": "mnemos-auto-refine",
                "hooks": [{
                    "type": "command",
                    "command": "python -m mnemos.auto_refine_hook --vault /path",
                    "timeout": 5,
                }],
            }]
        }
    }), encoding="utf-8")

    result = install_recall_hook(vault=tmp_path, uninstall=False)
    assert result.status in {"installed", "already-installed"}

    data = json.loads(settings.read_text(encoding="utf-8"))
    entries = data["hooks"]["SessionStart"]
    # Should have 2 entries now (auto-refine group + recall-briefing group)
    assert len(entries) == 2

    recall_groups = _recall_matches(entries)
    assert len(recall_groups) == 1
    recall_group = recall_groups[0]
    assert recall_group["_managed_by"] == RECALL_HOOK_MARKER
    assert recall_group["matcher"] == ""
    # Inner hooks list carries the actual command + timeout
    inner = recall_group["hooks"][0]
    assert inner["timeout"] == RECALL_HOOK_TIMEOUT_MS
    assert "recall_briefing" in inner["command"]
    assert "--vault" in inner["command"]


def test_install_recall_hook_idempotent(tmp_path: Path, monkeypatch) -> None:
    settings = tmp_path / "settings.json"
    monkeypatch.setattr("mnemos.recall_briefing.SETTINGS_PATH", settings)
    settings.write_text(json.dumps({"hooks": {"SessionStart": []}}), encoding="utf-8")

    install_recall_hook(vault=tmp_path, uninstall=False)
    r2 = install_recall_hook(vault=tmp_path, uninstall=False)
    assert r2.status == "already-installed"

    data = json.loads(settings.read_text(encoding="utf-8"))
    entries = data["hooks"]["SessionStart"]
    assert len(_recall_matches(entries)) == 1


def test_install_recall_hook_uninstall_removes_only_recall(tmp_path: Path, monkeypatch) -> None:
    settings = tmp_path / "settings.json"
    monkeypatch.setattr("mnemos.recall_briefing.SETTINGS_PATH", settings)
    install_recall_hook(vault=tmp_path, uninstall=False)

    # Add an unrelated hook group
    data = json.loads(settings.read_text(encoding="utf-8"))
    data["hooks"]["SessionStart"].append({
        "matcher": "",
        "_managed_by": "other-tool",
        "hooks": [{"type": "command", "command": "other", "timeout": 1000}],
    })
    settings.write_text(json.dumps(data), encoding="utf-8")

    result = install_recall_hook(vault=tmp_path, uninstall=True)
    assert result.status == "uninstalled"

    data = json.loads(settings.read_text(encoding="utf-8"))
    entries = data["hooks"]["SessionStart"]
    assert len(_recall_matches(entries)) == 0
    assert any(e.get("_managed_by") == "other-tool" for e in entries)


def test_install_recall_hook_vault_path_uses_forward_slashes_on_windows(
    tmp_path: Path, monkeypatch
) -> None:
    """Windows vault path in the command string uses forward slashes —
    mirrors auto_refine's workaround for Claude Code hook dispatcher
    eating \\P, \\m, \\s, \\a escape sequences."""
    import os as _os
    if _os.name != "nt":
        return  # not relevant off-Windows

    settings = tmp_path / "settings.json"
    monkeypatch.setattr("mnemos.recall_briefing.SETTINGS_PATH", settings)
    settings.write_text(json.dumps({"hooks": {"SessionStart": []}}), encoding="utf-8")

    install_recall_hook(vault=Path("C:\\Users\\alice\\vault"), uninstall=False)

    data = json.loads(settings.read_text(encoding="utf-8"))
    cmd = data["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert "C:/Users/alice/vault" in cmd
    assert "C:\\Users\\alice\\vault" not in cmd


def test_install_recall_hook_uninstall_not_present(tmp_path: Path, monkeypatch) -> None:
    settings = tmp_path / "settings.json"
    monkeypatch.setattr("mnemos.recall_briefing.SETTINGS_PATH", settings)
    result = install_recall_hook(vault=tmp_path, uninstall=True)
    assert result.status == "not-present"
