"""Tests for recall_mode yaml field."""
from __future__ import annotations

from pathlib import Path

from mnemos.config import MnemosConfig, load_config


def test_default_recall_mode_is_script(tmp_path: Path) -> None:
    (tmp_path / "mnemos.yaml").write_text("palace_root: Mnemos\n", encoding="utf-8")
    cfg = load_config(str(tmp_path))
    assert cfg.recall_mode == "script"


def test_load_recall_mode_skill(tmp_path: Path) -> None:
    (tmp_path / "mnemos.yaml").write_text(
        "palace_root: Mnemos\nrecall_mode: skill\n",
        encoding="utf-8",
    )
    cfg = load_config(str(tmp_path))
    assert cfg.recall_mode == "skill"


def test_missing_yaml_returns_default(tmp_path: Path) -> None:
    cfg = load_config(str(tmp_path))
    assert cfg.recall_mode == "script"


def test_dataclass_default() -> None:
    cfg = MnemosConfig(vault_path="/tmp")
    assert cfg.recall_mode == "script"
