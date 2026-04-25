"""Tests for mnemos.config — MnemosConfig dataclass and load_config()."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from mnemos.config import (
    HALLS_DEFAULT,
    WATCHER_IGNORE_DEFAULT,
    MnemosConfig,
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

        # v1.0: identity refresh defaults off
        assert cfg.auto_identity_refresh is False


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
            "auto_identity_refresh": True,
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
        assert cfg.auto_identity_refresh is True


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


# ---------------------------------------------------------------------------
# v1.0 narrative-first pivot — dead mining config fields scrubbed
# ---------------------------------------------------------------------------


class TestV1ConfigCleanup:
    """v1.0: legacy mining-bound config fields are gone; legacy yaml keys
    silently ignored on load (backward compat for users with stale yaml)."""

    def test_config_no_mine_mode_field(self, tmp_path: Path) -> None:
        """v1.0: mnemos.yaml mine_mode key is silently dropped on load."""
        (tmp_path / "Sessions").mkdir()
        yaml_content = (
            "languages: [en]\n"
            "search_backend: chromadb\n"
            "mine_mode: skill  # legacy field — should not crash; should be ignored\n"
            "mining_sources:\n"
            "  - {path: Sessions/, mode: session}\n"
            "chunk_max_size: 1234\n"
            "min_confidence: 0.99\n"
        )
        (tmp_path / "mnemos.yaml").write_text(yaml_content, encoding="utf-8")
        cfg = load_config(str(tmp_path))
        # The dataclass doesn't define these fields anymore; either
        # AttributeError on access or `not hasattr` is acceptable.
        assert not hasattr(cfg, "mine_mode") or cfg.mine_mode is None  # type: ignore[attr-defined]
        # Sanity: a still-supported field came through cleanly.
        assert cfg.languages == ["en"]
        assert cfg.search_backend == "chromadb"

    def test_config_auto_identity_refresh_default_false(self, tmp_vault: Path) -> None:
        """v1.0: auto_identity_refresh defaults to False."""
        cfg = MnemosConfig(vault_path=str(tmp_vault))
        assert cfg.auto_identity_refresh is False

    def test_config_no_legacy_mining_fields(self, tmp_vault: Path) -> None:
        """v1.0: dead mining config fields are gone from the dataclass."""
        cfg = MnemosConfig(vault_path=str(tmp_vault))
        for legacy in ("mining_sources", "chunk_max_size", "min_confidence", "mine_mode"):
            assert not hasattr(cfg, legacy), f"{legacy} still on Config"

    def test_load_config_does_not_import_mining_source(self) -> None:
        """v1.0: MiningSource dataclass is gone from mnemos.config."""
        import mnemos.config as cfg_mod

        assert not hasattr(cfg_mod, "MiningSource"), \
            "MiningSource dataclass should be removed in v1.0"
