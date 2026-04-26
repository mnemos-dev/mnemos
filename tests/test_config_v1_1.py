"""v1.1 config schema tests — schema_version + nested dataclasses + atomic save."""
from __future__ import annotations

from pathlib import Path

import yaml

from mnemos.config import load_config


def test_yaml_without_schema_version_loads_as_v2(tmp_path: Path) -> None:
    """v1 yaml (no schema_version field) must load with implicit version 2
    and v1.1 defaults injected at runtime — no file rewrite."""
    yaml_path = tmp_path / "mnemos.yaml"
    yaml_path.write_text(
        "search_backend: sqlite-vec\nrecall_mode: skill\n", encoding="utf-8"
    )
    cfg = load_config(str(tmp_path))
    assert cfg.schema_version == 2  # silently bumped at load
    # File on disk unchanged
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert "schema_version" not in raw, "must not auto-rewrite v1 yaml"


def test_yaml_with_schema_version_2_loads_directly(tmp_path: Path) -> None:
    yaml_path = tmp_path / "mnemos.yaml"
    yaml_path.write_text(
        "schema_version: 2\nsearch_backend: chromadb\n", encoding="utf-8"
    )
    cfg = load_config(str(tmp_path))
    assert cfg.schema_version == 2


def test_refine_config_defaults(tmp_path: Path) -> None:
    yaml_path = tmp_path / "mnemos.yaml"
    yaml_path.write_text("search_backend: chromadb\n", encoding="utf-8")
    cfg = load_config(str(tmp_path))
    assert cfg.refine.per_session == 3
    assert cfg.refine.direction == "newest"
    assert cfg.refine.min_user_turns == 3


def test_refine_config_from_yaml(tmp_path: Path) -> None:
    yaml_path = tmp_path / "mnemos.yaml"
    yaml_path.write_text(
        "schema_version: 2\nrefine:\n  per_session: 15\n  direction: oldest\n  min_user_turns: 5\n",
        encoding="utf-8",
    )
    cfg = load_config(str(tmp_path))
    assert cfg.refine.per_session == 15
    assert cfg.refine.direction == "oldest"
    assert cfg.refine.min_user_turns == 5
