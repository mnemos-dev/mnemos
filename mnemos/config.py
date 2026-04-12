"""Mnemos configuration — loads mnemos.yaml from vault root, falls back to defaults."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

HALLS_DEFAULT: List[str] = ["decisions", "facts", "events", "preferences", "problems"]

WATCHER_IGNORE_DEFAULT: List[str] = [
    ".obsidian/",
    "Mnemos/_recycled/",
    "*.canvas",
    "Templates/",
]


# ---------------------------------------------------------------------------
# Sub-dataclasses
# ---------------------------------------------------------------------------


@dataclass
class MiningSource:
    """A source path to mine for memory fragments."""

    path: str
    mode: str = "session"  # session | topic | chat
    external: bool = False  # True = outside vault, read-only, no watcher


# ---------------------------------------------------------------------------
# Main config dataclass
# ---------------------------------------------------------------------------


@dataclass
class MnemosConfig:
    """All configuration for a Mnemos instance."""

    # Core paths
    vault_path: str = ""
    palace_root: str = "Mnemos"
    recycled_dir: str = "_recycled"
    identity_dir: str = "_identity"

    # Language
    languages: List[str] = field(default_factory=lambda: ["en"])

    # LLM
    use_llm: bool = False
    llm_model: str = "claude-3-5-haiku-20241022"

    # Mining
    mining_sources: List[MiningSource] = field(default_factory=list)

    # Search
    search_limit: int = 10
    rerank: bool = False
    rerank_model: str = ""

    # Watcher
    watcher_enabled: bool = True
    watcher_ignore: List[str] = field(default_factory=lambda: list(WATCHER_IGNORE_DEFAULT))

    # Halls (memory categories)
    halls: List[str] = field(default_factory=lambda: list(HALLS_DEFAULT))

    # Internal paths (relative to vault_path / palace_root)
    chromadb_path: str = ".chroma"
    graph_path: str = "graph.json"
    mine_log_path: str = "mine.log"

    # ---------------------------------------------------------------------------
    # Derived path properties
    # ---------------------------------------------------------------------------

    @property
    def palace_dir(self) -> Path:
        """Absolute path to the palace root inside the vault."""
        return Path(self.vault_path) / self.palace_root

    @property
    def wings_dir(self) -> Path:
        """Absolute path to the wings directory (where halls live)."""
        return self.palace_dir / "wings"

    @property
    def recycled_full_path(self) -> Path:
        """Absolute path to the recycled fragments directory."""
        return self.palace_dir / self.recycled_dir

    @property
    def identity_full_path(self) -> Path:
        """Absolute path to the identity directory."""
        return self.palace_dir / self.identity_dir

    @property
    def chromadb_full_path(self) -> Path:
        """Absolute path to the ChromaDB data directory."""
        return self.palace_dir / self.chromadb_path

    @property
    def graph_full_path(self) -> Path:
        """Absolute path to the graph JSON file."""
        return self.palace_dir / self.graph_path

    @property
    def mine_log_full_path(self) -> Path:
        """Absolute path to the mine log file."""
        return self.palace_dir / self.mine_log_path


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_config(vault_path: Optional[str] = None) -> MnemosConfig:
    """Load MnemosConfig from mnemos.yaml in vault root.

    Falls back to defaults when the file does not exist or a key is absent.

    Args:
        vault_path: Explicit vault path. If None, reads MNEMOS_VAULT env var,
                    then falls back to an empty string (tests supply it later).
    """
    if vault_path is None:
        vault_path = os.environ.get("MNEMOS_VAULT", "")

    cfg = MnemosConfig(vault_path=vault_path)

    if not vault_path:
        return cfg

    yaml_path = Path(vault_path) / "mnemos.yaml"
    if not yaml_path.exists():
        return cfg

    with yaml_path.open("r", encoding="utf-8") as fh:
        raw: dict = yaml.safe_load(fh) or {}

    # Scalar fields
    for scalar in (
        "palace_root",
        "recycled_dir",
        "identity_dir",
        "use_llm",
        "llm_model",
        "search_limit",
        "rerank",
        "rerank_model",
        "watcher_enabled",
        "chromadb_path",
        "graph_path",
        "mine_log_path",
    ):
        if scalar in raw:
            setattr(cfg, scalar, raw[scalar])

    # List fields
    if "languages" in raw:
        cfg.languages = list(raw["languages"])

    if "halls" in raw:
        cfg.halls = list(raw["halls"])

    if "watcher_ignore" in raw:
        cfg.watcher_ignore = list(raw["watcher_ignore"])

    # Mining sources
    if "mining_sources" in raw:
        cfg.mining_sources = [
            MiningSource(
                path=src.get("path", ""),
                mode=src.get("mode", "session"),
                external=src.get("external", False),
            )
            for src in raw["mining_sources"]
            if isinstance(src, dict)
        ]

    return cfg
