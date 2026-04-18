"""Tests for wing canonicalization with TR diacritics and delimiters."""
from __future__ import annotations

from pathlib import Path

import pytest

from mnemos.config import MnemosConfig
from mnemos.palace import Palace, _normalize_for_match


def test_normalize_for_match_turkish_diacritics():
    assert _normalize_for_match("Satın Alma") == "satinalma"
    assert _normalize_for_match("SATIN_ALMA") == "satinalma"
    assert _normalize_for_match("satin-alma") == "satinalma"
    assert _normalize_for_match("Şirket") == "sirket"
    assert _normalize_for_match("İŞÇİ") == "isci"
    assert _normalize_for_match("Güney-Yıldızı") == "guneyyildizi"


def test_normalize_for_match_preserves_distinct_names():
    assert _normalize_for_match("Satın Alma") != _normalize_for_match("Satın Alma Otomasyonu")


def test_canonical_wing_matches_tr_variant(tmp_path: Path):
    cfg = MnemosConfig(vault_path=str(tmp_path))
    palace = Palace(cfg)
    palace.ensure_structure()

    palace.create_wing("Satın Alma")
    canonical_dir_name = (cfg.wings_dir / "Satın-Alma").name

    assert palace.canonical_wing("Satin-Alma") == canonical_dir_name
    assert palace.canonical_wing("SATIN ALMA") == canonical_dir_name
    assert palace.canonical_wing("satin_alma") == canonical_dir_name


def test_canonical_wing_no_match_returns_sanitized(tmp_path: Path):
    cfg = MnemosConfig(vault_path=str(tmp_path))
    palace = Palace(cfg)
    palace.ensure_structure()

    result = palace.canonical_wing("Brand New Wing")
    assert result == "Brand-New-Wing"


def test_canonical_wing_distinct_projects_not_merged(tmp_path: Path):
    cfg = MnemosConfig(vault_path=str(tmp_path))
    palace = Palace(cfg)
    palace.ensure_structure()

    palace.create_wing("Satın Alma")

    result = palace.canonical_wing("Satın Alma Otomasyonu")
    assert result != "Satın-Alma"
    assert result == "Satın-Alma-Otomasyonu"
