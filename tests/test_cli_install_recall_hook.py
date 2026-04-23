"""Tests for mnemos install-recall-hook CLI."""
from __future__ import annotations

import json
from pathlib import Path

from mnemos.recall_briefing import install_recall_hook, RECALL_HOOK_TIMEOUT_MS


def test_install_recall_hook_adds_session_start_entry(tmp_path: Path, monkeypatch) -> None:
    settings = tmp_path / "settings.json"
    monkeypatch.setattr("mnemos.recall_briefing.SETTINGS_PATH", settings)

    # Pre-seed with existing auto-refine hook
    settings.write_text(json.dumps({
        "hooks": {
            "SessionStart": [{
                "type": "command",
                "command": "python -m mnemos.auto_refine_hook",
                "timeout": 60000,
            }]
        }
    }), encoding="utf-8")

    result = install_recall_hook(vault=tmp_path, uninstall=False)
    assert result.status in {"installed", "already-installed"}

    data = json.loads(settings.read_text(encoding="utf-8"))
    entries = data["hooks"]["SessionStart"]
    # Should have 2 entries now (auto-refine + recall-briefing)
    assert len(entries) == 2
    recall_entry = next(e for e in entries if "recall_briefing" in e.get("command", ""))
    assert recall_entry["timeout"] == RECALL_HOOK_TIMEOUT_MS


def test_install_recall_hook_idempotent(tmp_path: Path, monkeypatch) -> None:
    settings = tmp_path / "settings.json"
    monkeypatch.setattr("mnemos.recall_briefing.SETTINGS_PATH", settings)
    settings.write_text(json.dumps({"hooks": {"SessionStart": []}}), encoding="utf-8")

    install_recall_hook(vault=tmp_path, uninstall=False)
    install_recall_hook(vault=tmp_path, uninstall=False)

    data = json.loads(settings.read_text(encoding="utf-8"))
    entries = [e for e in data["hooks"]["SessionStart"] if "recall_briefing" in e.get("command", "")]
    assert len(entries) == 1


def test_install_recall_hook_uninstall_removes_only_recall(tmp_path: Path, monkeypatch) -> None:
    settings = tmp_path / "settings.json"
    monkeypatch.setattr("mnemos.recall_briefing.SETTINGS_PATH", settings)
    install_recall_hook(vault=tmp_path, uninstall=False)

    # Also add unrelated hook
    data = json.loads(settings.read_text(encoding="utf-8"))
    data["hooks"]["SessionStart"].append({"type": "command", "command": "other"})
    settings.write_text(json.dumps(data), encoding="utf-8")

    install_recall_hook(vault=tmp_path, uninstall=True)

    data = json.loads(settings.read_text(encoding="utf-8"))
    entries = data["hooks"]["SessionStart"]
    assert not any("recall_briefing" in e.get("command", "") for e in entries)
    assert any(e.get("command") == "other" for e in entries)
