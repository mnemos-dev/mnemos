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


def test_briefing_config_defaults(tmp_path: Path) -> None:
    yaml_path = tmp_path / "mnemos.yaml"
    yaml_path.write_text("recall_mode: skill\n", encoding="utf-8")
    cfg = load_config(str(tmp_path))
    assert cfg.briefing.readiness_pct == 60
    assert cfg.briefing.show_systemmessage is True
    assert cfg.briefing.enforce_consistency is True


def test_briefing_config_from_yaml(tmp_path: Path) -> None:
    yaml_path = tmp_path / "mnemos.yaml"
    yaml_path.write_text(
        "schema_version: 2\nbriefing:\n  readiness_pct: 80\n  show_systemmessage: false\n  enforce_consistency: false\n",
        encoding="utf-8",
    )
    cfg = load_config(str(tmp_path))
    assert cfg.briefing.readiness_pct == 80
    assert cfg.briefing.show_systemmessage is False
    assert cfg.briefing.enforce_consistency is False


def test_identity_config_defaults(tmp_path: Path) -> None:
    yaml_path = tmp_path / "mnemos.yaml"
    yaml_path.write_text("search_backend: chromadb\n", encoding="utf-8")
    cfg = load_config(str(tmp_path))
    assert cfg.identity.bootstrap_threshold_pct == 25
    assert cfg.identity.auto_refresh is True
    assert cfg.identity.refresh_session_delta == 10
    assert cfg.identity.refresh_min_days == 7


def test_identity_config_from_yaml(tmp_path: Path) -> None:
    yaml_path = tmp_path / "mnemos.yaml"
    yaml_path.write_text(
        "schema_version: 2\nidentity:\n  bootstrap_threshold_pct: 50\n"
        "  auto_refresh: false\n  refresh_session_delta: 25\n  refresh_min_days: 14\n",
        encoding="utf-8",
    )
    cfg = load_config(str(tmp_path))
    assert cfg.identity.bootstrap_threshold_pct == 50
    assert cfg.identity.auto_refresh is False
    assert cfg.identity.refresh_session_delta == 25
    assert cfg.identity.refresh_min_days == 14
