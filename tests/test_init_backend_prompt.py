"""Tests for `mnemos init` backend selection prompt (v0.3.1 task 3.14a).

Covers the interactive backend picker, the platform-aware hint helper,
and the new i18n keys. The full `cmd_init` flow stays integration-tested
elsewhere; here we unit-test the small helpers and confirm the strings
round-trip through the i18n system in both locales.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from mnemos.cli import _ask_backend_choice, _resolve_backend_hint
from mnemos.i18n import SUPPORTED_LANGS, t


# ---------------------------------------------------------------------------
# _ask_backend_choice
# ---------------------------------------------------------------------------


def _fake_input(answers: list[str]):
    """Return a stub input() that yields answers in order."""
    it = iter(answers)
    return lambda _prompt="": next(it)


def test_ask_backend_choice_default_is_chromadb(monkeypatch, capsys) -> None:
    """Bare Enter keeps the status-quo default."""
    monkeypatch.setattr("builtins.input", _fake_input([""]))
    choice = _ask_backend_choice(lang="en")
    assert choice == "chromadb"


def test_ask_backend_choice_c_selects_chromadb(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", _fake_input(["C"]))
    assert _ask_backend_choice(lang="en") == "chromadb"


def test_ask_backend_choice_lower_c_selects_chromadb(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", _fake_input(["c"]))
    assert _ask_backend_choice(lang="en") == "chromadb"


def test_ask_backend_choice_s_selects_sqlite_vec(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", _fake_input(["S"]))
    assert _ask_backend_choice(lang="en") == "sqlite-vec"


def test_ask_backend_choice_invalid_input_reprompts(monkeypatch) -> None:
    """Garbage input loops until the user gives a valid answer."""
    monkeypatch.setattr(
        "builtins.input", _fake_input(["xyz", "42", "s"])
    )
    assert _ask_backend_choice(lang="en") == "sqlite-vec"


def test_ask_backend_choice_tr_locale_roundtrips(monkeypatch, capsys) -> None:
    """Turkish locale resolves correctly and accepts the same letter keys."""
    monkeypatch.setattr("builtins.input", _fake_input([""]))
    choice = _ask_backend_choice(lang="tr")
    assert choice == "chromadb"
    out = capsys.readouterr().out
    # At least one Turkish string should appear (not just English fallback)
    assert "sqlite-vec" in out


# ---------------------------------------------------------------------------
# _resolve_backend_hint (platform sniff)
# ---------------------------------------------------------------------------


def test_backend_hint_on_windows_py314_suggests_sqlite(monkeypatch) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr("sys.version_info", (3, 14, 0, "final", 0))
    hint = _resolve_backend_hint(lang="en")
    assert hint is not None
    assert "sqlite-vec" in hint.lower() or "[s]" in hint.lower()


def test_backend_hint_on_windows_py314_turkish(monkeypatch) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr("sys.version_info", (3, 14, 1, "final", 0))
    hint = _resolve_backend_hint(lang="tr")
    assert hint is not None
    assert hint.strip()  # non-empty translation


def test_backend_hint_returns_none_on_linux(monkeypatch) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("sys.version_info", (3, 14, 0, "final", 0))
    assert _resolve_backend_hint(lang="en") is None


def test_backend_hint_returns_none_on_windows_older_python(monkeypatch) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr("sys.version_info", (3, 12, 0, "final", 0))
    assert _resolve_backend_hint(lang="en") is None


# ---------------------------------------------------------------------------
# i18n key coverage — every new key must exist in both locales
# ---------------------------------------------------------------------------


_NEW_KEYS = (
    "backend.prompt_header",
    "backend.option_c",
    "backend.option_s",
    "backend.prompt",
    "backend.invalid",
    "backend.hint_windows_py314",
    "backend.chose_chromadb",
    "backend.chose_sqlite",
)


@pytest.mark.parametrize("key", _NEW_KEYS)
def test_backend_i18n_key_present_in_both_locales(key: str) -> None:
    for lang in SUPPORTED_LANGS:
        rendered = t(key, lang)
        assert isinstance(rendered, str) and rendered.strip()
