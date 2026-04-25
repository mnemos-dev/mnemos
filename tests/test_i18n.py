"""Tests for mnemos.i18n — locale-aware string lookup."""
from __future__ import annotations

import pytest

from mnemos.config import MnemosConfig
from mnemos.i18n import (
    DEFAULT_LANG,
    SUPPORTED_LANGS,
    resolve_lang,
    t,
)


class TestLookup:
    def test_default_lang_is_english(self) -> None:
        assert DEFAULT_LANG == "en"

    def test_supported_langs_include_en_tr(self) -> None:
        assert "en" in SUPPORTED_LANGS
        assert "tr" in SUPPORTED_LANGS

    def test_english_lookup(self) -> None:
        assert "Mnemos is your AI memory system" in t("intro.body", "en")

    def test_turkish_lookup(self) -> None:
        assert "AI hafıza sistemin" in t("intro.body", "tr")

    def test_missing_lang_falls_back_to_english(self) -> None:
        # Pretend the user picked German — we don't ship that yet.
        assert t("intro.body", "de") == t("intro.body", "en")

    def test_unknown_key_raises(self) -> None:
        with pytest.raises(KeyError):
            t("does.not.exist", "en")


class TestFormatting:
    def test_format_substitution_en(self) -> None:
        # per_source.header has all four substitution slots (sid, n, est, cls).
        out = t(
            "per_source.header", "en",
            sid="vault-sessions", n=42, est="2 min", cls="raw",
        )
        assert "vault-sessions" in out
        assert "42 files" in out

    def test_format_substitution_tr(self) -> None:
        out = t(
            "per_source.header", "tr",
            sid="vault-sessions", n=42, est="2 dk", cls="raw",
        )
        assert "vault-sessions" in out
        assert "42 dosya" in out

    def test_raw_registered_includes_path_and_skill(self) -> None:
        out = t("outcome.raw_registered", "en",
                sid="claude-code-jsonl", n=244, path="/x/y")
        assert "/mnemos-refine-transcripts" in out
        assert "/x/y" in out
        assert "244" in out


class TestResolveLang:
    def test_empty_languages_falls_back_to_en(self, tmp_path) -> None:
        cfg = MnemosConfig(vault_path=str(tmp_path), languages=[])
        assert resolve_lang(cfg) == "en"

    def test_first_supported_wins(self, tmp_path) -> None:
        cfg = MnemosConfig(vault_path=str(tmp_path), languages=["tr", "en"])
        assert resolve_lang(cfg) == "tr"

    def test_skips_unsupported(self, tmp_path) -> None:
        cfg = MnemosConfig(vault_path=str(tmp_path), languages=["zz", "tr"])
        assert resolve_lang(cfg) == "tr"

    def test_all_unsupported_falls_back_to_en(self, tmp_path) -> None:
        cfg = MnemosConfig(vault_path=str(tmp_path), languages=["zz", "qq"])
        assert resolve_lang(cfg) == "en"


class TestStringCoverage:
    """Sanity check: every key has both EN and TR (regression guard)."""

    def test_all_keys_have_en_and_tr(self) -> None:
        from mnemos.i18n import _STRINGS

        missing = []
        for key, bundle in _STRINGS.items():
            for lang in ("en", "tr"):
                if lang not in bundle:
                    missing.append(f"{key}:{lang}")
        assert not missing, f"Missing translations: {missing}"
