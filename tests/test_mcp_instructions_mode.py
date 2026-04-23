"""Tests for mnemos.server.build_instructions — recall_mode-aware."""
from __future__ import annotations

from mnemos.config import MnemosConfig
from mnemos.server import build_instructions


def _cfg(recall_mode: str) -> MnemosConfig:
    return MnemosConfig(vault_path="/tmp", recall_mode=recall_mode)


def test_script_mode_mentions_mnemos_search_auto_call() -> None:
    out = build_instructions(_cfg("script"))
    assert "mnemos_wake_up" in out
    assert "mnemos_search" in out
    # Script mode = AI auto-calls when relevant
    assert "retrieve relevant memories" in out or "when relevant" in out


def test_skill_mode_mentions_briefing_injected() -> None:
    out = build_instructions(_cfg("skill"))
    assert "briefing" in out.lower()
    assert "additionalContext" in out or "already injected" in out


def test_skill_mode_discourages_auto_search() -> None:
    out = build_instructions(_cfg("skill"))
    # Should discourage auto-call but allow user-explicit ask
    assert "auto-call" in out.lower() or "auto-search" in out.lower() or "Do NOT" in out
    assert "explicit" in out.lower() or "user" in out.lower()


def test_unknown_mode_falls_back_to_script() -> None:
    out = build_instructions(_cfg("nonsense"))
    assert "mnemos_wake_up" in out
    assert "mnemos_search" in out


def test_default_config_produces_script_instructions() -> None:
    out = build_instructions(MnemosConfig(vault_path="/tmp"))
    assert "mnemos_search" in out
