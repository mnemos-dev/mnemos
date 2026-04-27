"""mnemos init v1.1 phases — refine quota dialog + install-end-hook prompt."""
from __future__ import annotations

from pathlib import Path

import pytest


def test_init_refine_quota_dialog_returns_dict_with_validated_values(monkeypatch):
    from mnemos.cli import _init_refine_quota_dialog

    inputs = iter(["15", "n", "5"])
    monkeypatch.setattr("builtins.input", lambda *a, **kw: next(inputs))

    out = _init_refine_quota_dialog(vault=Path("."), eligible_count=120, lang="en")
    assert out["per_session"] == 15
    assert out["direction"] == "newest"
    assert out["min_user_turns"] == 5


def test_init_refine_quota_dialog_accepts_oldest_and_long_words(monkeypatch):
    """Direction prompt accepts 'o' / 'oldest' / 'newest' (full word)."""
    from mnemos.cli import _init_refine_quota_dialog

    inputs = iter(["3", "oldest", "3"])
    monkeypatch.setattr("builtins.input", lambda *a, **kw: next(inputs))

    out = _init_refine_quota_dialog(vault=Path("."), eligible_count=10, lang="en")
    assert out["direction"] == "oldest"


def test_init_refine_quota_dialog_uses_defaults_on_empty_input(monkeypatch):
    from mnemos.cli import _init_refine_quota_dialog

    inputs = iter(["", "", ""])
    monkeypatch.setattr("builtins.input", lambda *a, **kw: next(inputs))

    out = _init_refine_quota_dialog(vault=Path("."), eligible_count=0, lang="en")
    assert out["per_session"] == 3
    assert out["direction"] == "newest"
    assert out["min_user_turns"] == 3


def test_init_refine_quota_dialog_rejects_out_of_range(monkeypatch):
    """First per_session attempt 999 (out of range) -> retry; second 10 OK."""
    from mnemos.cli import _init_refine_quota_dialog

    inputs = iter(["999", "10", "n", "3"])
    monkeypatch.setattr("builtins.input", lambda *a, **kw: next(inputs))

    out = _init_refine_quota_dialog(vault=Path("."), eligible_count=0, lang="en")
    assert out["per_session"] == 10


def test_init_prompt_install_end_hook_invokes_cmd_when_y(monkeypatch, tmp_path):
    from mnemos.cli import _init_prompt_install_end_hook

    monkeypatch.setattr("builtins.input", lambda *a, **kw: "y")
    called: list = []
    monkeypatch.setattr(
        "mnemos.cli.cmd_install_end_hook",
        lambda ns: called.append((ns.vault, ns.uninstall, ns.v1)) or 0,
    )
    _init_prompt_install_end_hook(vault=tmp_path, lang="en")
    assert len(called) == 1
    assert called[0] == (str(tmp_path), False, True)


def test_init_prompt_install_end_hook_skips_when_n(monkeypatch, tmp_path):
    from mnemos.cli import _init_prompt_install_end_hook

    monkeypatch.setattr("builtins.input", lambda *a, **kw: "n")
    called: list = []
    monkeypatch.setattr(
        "mnemos.cli.cmd_install_end_hook",
        lambda ns: called.append(True) or 0,
    )
    _init_prompt_install_end_hook(vault=tmp_path, lang="en")
    assert called == []
