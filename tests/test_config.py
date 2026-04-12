"""Tests for mnemos.config — MnemosConfig dataclass and load_config()."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from mnemos.config import (
    HALLS_DEFAULT,
    WATCHER_IGNORE_DEFAULT,
    MnemosConfig,
    MiningSource,
    load_config,
)


class TestDefaultConfig:
    """test_default_config — verify defaults when no yaml exists."""

    def test_default_config(self, tmp_vault: Path) -> None:
        cfg = load_config(str(tmp_vault))

        # Core paths
        assert cfg.vault_path == str(tmp_vault)
        assert cfg.palace_root == "Mnemos"
        assert cfg.recycled_dir == "_recycled"
        assert cfg.identity_dir == "_identity"

        # Language
        assert cfg.languages == ["en"]

        # LLM off by default
        assert cfg.use_llm is False
        assert cfg.llm_model == "claude-3-5-haiku-20241022"

        # Mining empty by default
        assert cfg.mining_sources == []

        # Search defaults
        assert cfg.search_limit == 10
        assert cfg.rerank is False

        # Watcher on by default
        assert cfg.watcher_enabled is True
        assert cfg.watcher_ignore == WATCHER_IGNORE_DEFAULT

        # Halls
        assert cfg.halls == HALLS_DEFAULT

        # Internal paths
        assert cfg.chromadb_path == ".chroma"
        assert cfg.graph_path == "graph.json"
        assert cfg.mine_log_path == "mine.log"


class TestLoadFromYaml:
    """test_load_from_yaml — verify loading from mnemos.yaml."""

    def test_load_from_yaml(self, tmp_vault: Path) -> None:
        yaml_data = {
            "palace_root": "Memory",
            "languages": ["tr", "en"],
            "use_llm": True,
            "llm_model": "claude-3-5-sonnet-20241022",
            "search_limit": 20,
            "rerank": True,
            "rerank_model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
            "watcher_enabled": False,
            "halls": ["decisions", "facts"],
            "watcher_ignore": [".obsidian/", "*.canvas"],
            "mining_sources": [
                {"path": "Sessions/", "mode": "session"},
                {"path": "Topics/", "mode": "topic"},
            ],
        }
        (tmp_vault / "mnemos.yaml").write_text(
            yaml.dump(yaml_data), encoding="utf-8"
        )

        cfg = load_config(str(tmp_vault))

        assert cfg.palace_root == "Memory"
        assert cfg.languages == ["tr", "en"]
        assert cfg.use_llm is True
        assert cfg.llm_model == "claude-3-5-sonnet-20241022"
        assert cfg.search_limit == 20
        assert cfg.rerank is True
        assert cfg.rerank_model == "cross-encoder/ms-marco-MiniLM-L-6-v2"
        assert cfg.watcher_enabled is False
        assert cfg.halls == ["decisions", "facts"]
        assert cfg.watcher_ignore == [".obsidian/", "*.canvas"]

        assert len(cfg.mining_sources) == 2
        assert cfg.mining_sources[0] == MiningSource(path="Sessions/", mode="session")
        assert cfg.mining_sources[1] == MiningSource(path="Topics/", mode="topic")


class TestConfigPathProperties:
    """test_config_path_properties — verify derived path properties."""

    def test_config_path_properties(self, config: MnemosConfig, tmp_vault: Path) -> None:
        vault = Path(config.vault_path)

        assert config.palace_dir == vault / "Mnemos"
        assert config.wings_dir == vault / "Mnemos" / "wings"
        assert config.recycled_full_path == vault / "Mnemos" / "_recycled"
        assert config.identity_full_path == vault / "Mnemos" / "_identity"
        assert config.chromadb_full_path == vault / "Mnemos" / ".chroma"
        assert config.graph_full_path == vault / "Mnemos" / "graph.json"
        assert config.mine_log_full_path == vault / "Mnemos" / "mine.log"

    def test_custom_palace_root_changes_derived_paths(self, tmp_vault: Path) -> None:
        cfg = MnemosConfig(vault_path=str(tmp_vault), palace_root="Palace")

        assert cfg.palace_dir == tmp_vault / "Palace"
        assert cfg.wings_dir == tmp_vault / "Palace" / "wings"
        assert cfg.recycled_full_path == tmp_vault / "Palace" / "_recycled"
