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


def test_create_room_does_not_pre_create_hall_dirs(tmp_path: Path):
    cfg = MnemosConfig(vault_path=str(tmp_path))
    palace = Palace(cfg)
    palace.ensure_structure()

    room_dir = palace.create_room("TestWing", "testroom")
    assert room_dir.exists()

    for hall in cfg.halls:
        assert not (room_dir / hall).exists(), \
            f"hall {hall} should NOT be pre-created"


def test_add_drawer_creates_hall_lazily(tmp_path: Path):
    cfg = MnemosConfig(vault_path=str(tmp_path))
    palace = Palace(cfg)
    palace.ensure_structure()

    palace.add_drawer(
        wing="TestWing", room="testroom", hall="decisions",
        text="A decision", source="src.md", importance=0.5,
        entities=[], language="en",
    )

    room_dir = cfg.wings_dir / "TestWing" / "testroom"
    assert (room_dir / "decisions").exists()
    for hall in cfg.halls:
        if hall != "decisions":
            assert not (room_dir / hall).exists(), \
                f"unused hall {hall} should not exist"


def test_wing_summary_written_on_first_drawer_not_upfront(tmp_path: Path):
    cfg = MnemosConfig(vault_path=str(tmp_path))
    palace = Palace(cfg)
    palace.ensure_structure()

    palace.create_wing("LazyWing")
    assert not (cfg.wings_dir / "LazyWing" / "_wing.md").exists(), \
        "_wing.md should not exist until first drawer"

    palace.add_drawer(
        wing="LazyWing", room="general", hall="facts",
        text="Hello", source="src.md", importance=0.5,
        entities=[], language="en",
    )
    assert (cfg.wings_dir / "LazyWing" / "_wing.md").exists()
    assert (cfg.wings_dir / "LazyWing" / "general" / "_room.md").exists()
