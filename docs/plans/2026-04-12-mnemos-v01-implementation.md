# Mnemos v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working Obsidian-native AI memory palace with semantic search, hybrid mining, file watcher, and MCP server — installable via `pip install mnemos`.

**Architecture:** Monolithic Python MCP server. Every memory is dual-stored: Obsidian `.md` file (master) + ChromaDB vector (index). A file watcher keeps them in sync. Mining uses regex patterns with optional Claude API enhancement.

**Tech Stack:** Python 3.10+, ChromaDB, MCP SDK, watchdog, PyYAML, anthropic (optional)

**Spec:** `docs/specs/2026-04-12-mnemos-design.md`

---

## File Map

| File | Responsibility |
|------|---------------|
| `pyproject.toml` | Package definition, dependencies, CLI entry point |
| `LICENSE` | MIT license |
| `mnemos/__init__.py` | Version export |
| `mnemos/__main__.py` | `python -m mnemos.server` entry point |
| `mnemos/config.py` | Load and validate `mnemos.yaml` |
| `mnemos/palace.py` | Wing/Room/Hall CRUD — create folders, read/write drawer .md files |
| `mnemos/obsidian.py` | Obsidian-specific I/O: frontmatter parse/write, vault path resolution |
| `mnemos/search.py` | ChromaDB indexing + 3-layer search (metadata → semantic → rerank) |
| `mnemos/graph.py` | SQLite knowledge graph — entities, triples, temporal queries |
| `mnemos/miner.py` | Hybrid mining: regex patterns + optional Claude API extraction |
| `mnemos/watcher.py` | File watcher: detect changes, trigger re-index/delete |
| `mnemos/stack.py` | L0-L3 memory stack: identity, summaries, recall, deep search |
| `mnemos/server.py` | MCP server: 8 tools exposed via MCP protocol |
| `mnemos/cli.py` | CLI commands: `mnemos init`, `mnemos mine`, `mnemos search`, `mnemos status` |
| `mnemos/patterns/base.yaml` | Language-independent patterns (dates, URLs, wikilinks) |
| `mnemos/patterns/tr.yaml` | Turkish regex patterns |
| `mnemos/patterns/en.yaml` | English regex patterns |
| `tests/conftest.py` | Shared fixtures: tmp vault, sample files, ChromaDB in-memory |
| `tests/test_config.py` | Config loading tests |
| `tests/test_obsidian.py` | Frontmatter parse/write tests |
| `tests/test_palace.py` | Wing/Room/Hall CRUD tests |
| `tests/test_search.py` | ChromaDB indexing + search tests |
| `tests/test_graph.py` | Knowledge graph tests |
| `tests/test_miner.py` | Mining regex + chunking tests |
| `tests/test_watcher.py` | File watcher event tests |
| `tests/test_stack.py` | Memory stack L0-L3 tests |
| `tests/test_server.py` | MCP server tool integration tests |
| `tests/test_integration.py` | End-to-end: mine → search → graph full cycle |
| `tests/fixtures/sample_session_tr.md` | Turkish session log fixture |
| `tests/fixtures/sample_session_en.md` | English session log fixture |
| `tests/fixtures/sample_topic.md` | Topic note fixture |

---

## Task 1: Project Scaffolding + Config

**Files:**
- Create: `pyproject.toml`
- Create: `LICENSE`
- Create: `mnemos/__init__.py`
- Create: `mnemos/config.py`
- Create: `tests/conftest.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Install missing dependencies**

```bash
pip install watchdog mcp
```

Expected: Both packages install successfully.

- [ ] **Step 2: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "mnemos"
version = "0.1.0"
description = "Obsidian-native AI memory palace with semantic search"
readme = "README.md"
license = "MIT"
requires-python = ">=3.10"
authors = [
    {name = "Tugra Demirors", email = "tugra@gypenergy.com"},
]
keywords = ["obsidian", "memory", "ai", "mcp", "chromadb"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
]
dependencies = [
    "chromadb>=1.0",
    "mcp>=1.0",
    "watchdog>=4.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
llm = ["anthropic>=0.40"]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]

[project.scripts]
mnemos = "mnemos.cli:main"
```

- [ ] **Step 3: Create LICENSE (MIT)**

```
MIT License

Copyright (c) 2026 Tugra Demirors / GYP Energy

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 4: Create mnemos/__init__.py**

```python
"""Mnemos — Obsidian-native AI memory palace."""

__version__ = "0.1.0"
```

- [ ] **Step 5: Create mnemos/config.py**

```python
"""Load and validate mnemos.yaml configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


HALLS_DEFAULT = ["decisions", "facts", "events", "preferences", "problems"]

WATCHER_IGNORE_DEFAULT = [
    ".obsidian/",
    "Mnemos/_recycled/",
    "*.canvas",
    "Templates/",
]


@dataclass
class MiningSource:
    path: str
    mode: str = "auto"  # auto | sessions | general | project | skip


@dataclass
class MnemosConfig:
    vault_path: Path
    palace_root: str = "Mnemos"
    recycled_dir: str = "Mnemos/_recycled"
    identity_dir: str = "Mnemos/Identity"
    languages: list[str] = field(default_factory=lambda: ["en"])
    use_llm: bool = False
    llm_model: str = "claude-sonnet-4-6"
    mining_sources: list[MiningSource] = field(default_factory=list)
    search_limit: int = 5
    rerank: bool = True
    rerank_model: str = "claude-haiku-4-5"
    watcher_enabled: bool = True
    watcher_ignore: list[str] = field(default_factory=lambda: list(WATCHER_IGNORE_DEFAULT))
    halls: list[str] = field(default_factory=lambda: list(HALLS_DEFAULT))
    chromadb_path: str = "Mnemos/.chromadb"
    graph_path: str = "Mnemos/.graph.db"
    mine_log_path: str = "Mnemos/.mine_log.json"

    @property
    def palace_dir(self) -> Path:
        return self.vault_path / self.palace_root

    @property
    def wings_dir(self) -> Path:
        return self.palace_dir / "Wings"

    @property
    def recycled_full_path(self) -> Path:
        return self.vault_path / self.recycled_dir

    @property
    def identity_full_path(self) -> Path:
        return self.vault_path / self.identity_dir

    @property
    def chromadb_full_path(self) -> Path:
        return self.vault_path / self.chromadb_path

    @property
    def graph_full_path(self) -> Path:
        return self.vault_path / self.graph_path

    @property
    def mine_log_full_path(self) -> Path:
        return self.vault_path / self.mine_log_path


def load_config(vault_path: str | Path | None = None) -> MnemosConfig:
    """Load config from mnemos.yaml in the vault root.

    If vault_path is None, looks for MNEMOS_VAULT env var,
    then tries current directory.
    """
    if vault_path is None:
        vault_path = os.environ.get("MNEMOS_VAULT", ".")
    vault_path = Path(vault_path).resolve()

    config_file = vault_path / "mnemos.yaml"
    if not config_file.exists():
        return MnemosConfig(vault_path=vault_path)

    with open(config_file, "r", encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    mining_raw = raw.get("mining", {})
    sources_raw = mining_raw.get("sources", [])
    sources = [MiningSource(path=s["path"], mode=s.get("mode", "auto")) for s in sources_raw]

    vault_cfg = raw.get("vault", {})
    resolved_vault = Path(vault_cfg.get("path", str(vault_path))).resolve()

    palace_cfg = raw.get("palace", {})
    search_cfg = raw.get("search", {})
    watcher_cfg = raw.get("watcher", {})
    storage_cfg = raw.get("storage", {})

    return MnemosConfig(
        vault_path=resolved_vault,
        palace_root=palace_cfg.get("root", "Mnemos"),
        recycled_dir=palace_cfg.get("recycled", "Mnemos/_recycled"),
        identity_dir=palace_cfg.get("identity", "Mnemos/Identity"),
        languages=mining_raw.get("languages", ["en"]),
        use_llm=mining_raw.get("use_llm", False),
        llm_model=mining_raw.get("llm_model", "claude-sonnet-4-6"),
        mining_sources=sources,
        search_limit=search_cfg.get("default_limit", 5),
        rerank=search_cfg.get("rerank", True),
        rerank_model=search_cfg.get("rerank_model", "claude-haiku-4-5"),
        watcher_enabled=watcher_cfg.get("enabled", True),
        watcher_ignore=watcher_cfg.get("ignore", list(WATCHER_IGNORE_DEFAULT)),
        halls=raw.get("halls", list(HALLS_DEFAULT)),
        chromadb_path=storage_cfg.get("chromadb_path", "Mnemos/.chromadb"),
        graph_path=storage_cfg.get("graph_path", "Mnemos/.graph.db"),
        mine_log_path=storage_cfg.get("mine_log", "Mnemos/.mine_log.json"),
    )
```

- [ ] **Step 6: Create tests/conftest.py**

```python
"""Shared test fixtures for Mnemos."""

import shutil
from pathlib import Path

import pytest

from mnemos.config import MnemosConfig


@pytest.fixture
def tmp_vault(tmp_path: Path) -> Path:
    """Create a temporary vault directory with basic structure."""
    vault = tmp_path / "test_vault"
    vault.mkdir()
    (vault / "Sessions").mkdir()
    (vault / "Topics").mkdir()
    return vault


@pytest.fixture
def config(tmp_vault: Path) -> MnemosConfig:
    """Create a MnemosConfig pointing at the temporary vault."""
    return MnemosConfig(
        vault_path=tmp_vault,
        languages=["tr", "en"],
    )


@pytest.fixture
def sample_session_tr(tmp_vault: Path) -> Path:
    """Create a Turkish session log fixture."""
    content = """---
project: ProcureTrack
tags: [approval, supabase]
date: 2026-04-08
---

# ProcureTrack Approval Flow

## Ozet
Bugun approval flow uzerinde calistik. Supabase RLS ile gitmeye karar verdik.

## Yapilan Isler
- Approval flow icin Supabase RLS policy olusturuldu
- Her kullanici sadece kendi departmaninin PO'larini gorebilecek
- Manager rolu tum departmanlari gorebilir
- Hata: RLS policy ilk denemede calismadi, cozum olarak service_role key kullanildi

## Kararlar
- Supabase RLS tercih ettik cunku row-level guvenlik saglıyor
- Tercihimiz her zaman server-side validation kullanmak

## Sonraki Adimlar
- Revision mekanizmasi eklenecek
- Test suite yazilacak
"""
    filepath = tmp_vault / "Sessions" / "2026-04-08-ProcureTrack-approval.md"
    filepath.write_text(content, encoding="utf-8")
    return filepath


@pytest.fixture
def sample_session_en(tmp_vault: Path) -> Path:
    """Create an English session log fixture."""
    content = """---
project: LightRAG
tags: [graphrag, cost]
date: 2026-04-04
---

# LightRAG Cost Crisis

## Summary
We decided to shut down the Google Gemini pipeline after the bill hit 1125 TL.
Switched to Anthropic Claude for embeddings.

## Problems
- Bug: Gemini API was called without rate limiting
- The solution is to add a cost ceiling per day

## Decisions
- We chose Anthropic over OpenAI for cost reasons
- Always use batch mode for embeddings to save money

## Next Steps
- Migrate remaining 20 PO documents
- Set up daily cost alerts
"""
    filepath = tmp_vault / "Sessions" / "2026-04-04-LightRAG-cost.md"
    filepath.write_text(content, encoding="utf-8")
    return filepath


@pytest.fixture
def sample_topic(tmp_vault: Path) -> Path:
    """Create a topic note fixture."""
    content = """---
project: ProcureTrack
status: active
---

# ProcureTrack

Next.js 14 + Supabase tabanli satin alma yonetim sistemi.
GYP Energy icin gelistiriliyor.

## Ozellikler
- RFQ olusturma ve yonetimi
- Teklif karsilastirma
- PO olusturma
- Approval workflow
"""
    filepath = tmp_vault / "Topics" / "ProcureTrack.md"
    filepath.write_text(content, encoding="utf-8")
    return filepath
```

- [ ] **Step 7: Write config tests**

```python
"""Tests for mnemos.config."""

from pathlib import Path

import yaml

from mnemos.config import MnemosConfig, load_config, HALLS_DEFAULT


def test_default_config(tmp_vault: Path):
    """Config with no yaml file uses sensible defaults."""
    cfg = load_config(tmp_vault)
    assert cfg.vault_path == tmp_vault
    assert cfg.palace_root == "Mnemos"
    assert cfg.halls == HALLS_DEFAULT
    assert cfg.wings_dir == tmp_vault / "Mnemos" / "Wings"


def test_load_from_yaml(tmp_vault: Path):
    """Config loads values from mnemos.yaml."""
    config_data = {
        "version": 1,
        "vault": {"path": str(tmp_vault)},
        "palace": {"root": "MyPalace"},
        "mining": {
            "languages": ["tr", "en"],
            "use_llm": True,
            "sources": [
                {"path": "Sessions/", "mode": "sessions"},
                {"path": "Topics/", "mode": "general"},
            ],
        },
        "halls": ["decisions", "facts", "custom_hall"],
        "search": {"default_limit": 10, "rerank": False},
        "storage": {"chromadb_path": "MyPalace/.chroma"},
    }
    config_file = tmp_vault / "mnemos.yaml"
    config_file.write_text(yaml.dump(config_data), encoding="utf-8")

    cfg = load_config(tmp_vault)
    assert cfg.palace_root == "MyPalace"
    assert cfg.languages == ["tr", "en"]
    assert cfg.use_llm is True
    assert len(cfg.mining_sources) == 2
    assert cfg.mining_sources[0].mode == "sessions"
    assert cfg.halls == ["decisions", "facts", "custom_hall"]
    assert cfg.search_limit == 10
    assert cfg.rerank is False
    assert cfg.chromadb_path == "MyPalace/.chroma"


def test_config_path_properties(tmp_vault: Path):
    """Derived path properties resolve correctly."""
    cfg = MnemosConfig(vault_path=tmp_vault)
    assert cfg.palace_dir == tmp_vault / "Mnemos"
    assert cfg.wings_dir == tmp_vault / "Mnemos" / "Wings"
    assert cfg.recycled_full_path == tmp_vault / "Mnemos" / "_recycled"
    assert cfg.identity_full_path == tmp_vault / "Mnemos" / "Identity"
    assert cfg.chromadb_full_path == tmp_vault / "Mnemos" / ".chromadb"
    assert cfg.graph_full_path == tmp_vault / "Mnemos" / ".graph.db"
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
cd C:/Projeler/mnemos && pip install -e ".[dev]" && pytest tests/test_config.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 9: Commit**

```bash
cd C:/Projeler/mnemos
git add pyproject.toml LICENSE mnemos/__init__.py mnemos/config.py tests/conftest.py tests/test_config.py
git commit -m "feat: project scaffolding + config module with tests"
```

---

## Task 2: Obsidian I/O (Frontmatter Parse/Write)

**Files:**
- Create: `mnemos/obsidian.py`
- Create: `tests/test_obsidian.py`

- [ ] **Step 1: Write failing tests for frontmatter parsing and writing**

```python
"""Tests for mnemos.obsidian."""

from pathlib import Path

from mnemos.obsidian import parse_drawer_file, write_drawer_file, parse_frontmatter


def test_parse_frontmatter(tmp_path: Path):
    """Parse YAML frontmatter from a markdown file."""
    content = """---
wing: TestProject
room: auth
hall: decisions
---

Some content here.
"""
    filepath = tmp_path / "test.md"
    filepath.write_text(content, encoding="utf-8")

    meta, body = parse_frontmatter(filepath)
    assert meta["wing"] == "TestProject"
    assert meta["room"] == "auth"
    assert meta["hall"] == "decisions"
    assert body.strip() == "Some content here."


def test_parse_frontmatter_no_frontmatter(tmp_path: Path):
    """Files without frontmatter return empty dict."""
    filepath = tmp_path / "plain.md"
    filepath.write_text("Just plain text.", encoding="utf-8")

    meta, body = parse_frontmatter(filepath)
    assert meta == {}
    assert body.strip() == "Just plain text."


def test_write_drawer_file(tmp_path: Path):
    """Write a drawer .md file with frontmatter."""
    filepath = tmp_path / "drawer.md"
    metadata = {
        "wing": "ProcureTrack",
        "room": "approval-flow",
        "hall": "decisions",
        "source": "Sessions/2026-04-08.md",
        "importance": 0.8,
        "entities": ["ProcureTrack", "Supabase"],
        "language": "tr",
    }
    body = "Supabase RLS ile gitmeye karar verdik."

    write_drawer_file(filepath, metadata, body)

    assert filepath.exists()
    parsed_meta, parsed_body = parse_frontmatter(filepath)
    assert parsed_meta["wing"] == "ProcureTrack"
    assert parsed_meta["importance"] == 0.8
    assert parsed_meta["entities"] == ["ProcureTrack", "Supabase"]
    assert parsed_body.strip() == body


def test_parse_drawer_file(tmp_path: Path):
    """parse_drawer_file returns a structured dict."""
    filepath = tmp_path / "drawer.md"
    content = """---
wing: LightRAG
room: cost
hall: problems
source: Sessions/2026-04-04.md
importance: 0.6
entities: [Gemini, Anthropic]
language: en
---

Gemini API cost hit 1125 TL without rate limiting.
"""
    filepath.write_text(content, encoding="utf-8")

    drawer = parse_drawer_file(filepath)
    assert drawer["wing"] == "LightRAG"
    assert drawer["hall"] == "problems"
    assert "1125 TL" in drawer["text"]
    assert drawer["entities"] == ["Gemini", "Anthropic"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd C:/Projeler/mnemos && pytest tests/test_obsidian.py -v
```

Expected: FAIL — `mnemos.obsidian` does not exist.

- [ ] **Step 3: Implement mnemos/obsidian.py**

```python
"""Obsidian vault I/O: frontmatter parsing and drawer file management."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def parse_frontmatter(filepath: Path) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter and body from a markdown file.

    Returns (metadata_dict, body_text). If no frontmatter, returns ({}, full_text).
    """
    text = filepath.read_text(encoding="utf-8")

    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    raw_yaml = parts[1].strip()
    body = parts[2].strip()

    try:
        metadata = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError:
        return {}, text

    return metadata, body


def write_drawer_file(
    filepath: Path,
    metadata: dict[str, Any],
    body: str,
) -> None:
    """Write a drawer markdown file with YAML frontmatter."""
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Add mined_at if not present
    if "mined_at" not in metadata:
        metadata["mined_at"] = datetime.now(timezone.utc).isoformat()

    yaml_str = yaml.dump(metadata, default_flow_style=False, allow_unicode=True, sort_keys=False)
    content = f"---\n{yaml_str}---\n\n{body}\n"
    filepath.write_text(content, encoding="utf-8")


def parse_drawer_file(filepath: Path) -> dict[str, Any]:
    """Parse a drawer file into a structured dict.

    Returns dict with keys: wing, room, hall, text, source, importance,
    entities, language, mined_at, filepath.
    """
    metadata, body = parse_frontmatter(filepath)
    return {
        "wing": metadata.get("wing", ""),
        "room": metadata.get("room", ""),
        "hall": metadata.get("hall", ""),
        "text": body,
        "source": metadata.get("source", ""),
        "importance": metadata.get("importance", 0.5),
        "entities": metadata.get("entities", []),
        "language": metadata.get("language", ""),
        "mined_at": metadata.get("mined_at", ""),
        "filepath": str(filepath),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd C:/Projeler/mnemos && pytest tests/test_obsidian.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd C:/Projeler/mnemos
git add mnemos/obsidian.py tests/test_obsidian.py
git commit -m "feat: obsidian I/O with frontmatter parse/write"
```

---

## Task 3: Palace Structure (Wing/Room/Hall CRUD)

**Files:**
- Create: `mnemos/palace.py`
- Create: `tests/test_palace.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for mnemos.palace."""

from pathlib import Path

from mnemos.config import MnemosConfig
from mnemos.palace import Palace


def test_ensure_structure(config: MnemosConfig):
    """ensure_structure creates Mnemos/, Wings/, Identity/, _recycled/."""
    palace = Palace(config)
    palace.ensure_structure()

    assert config.wings_dir.exists()
    assert config.identity_full_path.exists()
    assert config.recycled_full_path.exists()


def test_create_wing(config: MnemosConfig):
    """create_wing creates wing directory with _wing.md."""
    palace = Palace(config)
    palace.ensure_structure()
    palace.create_wing("ProcureTrack")

    wing_dir = config.wings_dir / "ProcureTrack"
    assert wing_dir.exists()
    assert (wing_dir / "_wing.md").exists()


def test_create_room(config: MnemosConfig):
    """create_room creates room directory with _room.md."""
    palace = Palace(config)
    palace.ensure_structure()
    palace.create_wing("ProcureTrack")
    palace.create_room("ProcureTrack", "approval-flow")

    room_dir = config.wings_dir / "ProcureTrack" / "approval-flow"
    assert room_dir.exists()
    assert (room_dir / "_room.md").exists()
    # Halls should be created
    for hall in config.halls:
        assert (room_dir / hall).is_dir()


def test_add_drawer(config: MnemosConfig):
    """add_drawer creates a .md file in the correct hall."""
    palace = Palace(config)
    palace.ensure_structure()

    drawer_path = palace.add_drawer(
        wing="ProcureTrack",
        room="approval-flow",
        hall="decisions",
        text="Supabase RLS ile gitmeye karar verdik.",
        source="Sessions/2026-04-08.md",
        importance=0.8,
        entities=["ProcureTrack", "Supabase"],
        language="tr",
    )

    assert drawer_path.exists()
    assert "ProcureTrack" in str(drawer_path)
    assert "approval-flow" in str(drawer_path)
    assert "decisions" in str(drawer_path)


def test_list_wings(config: MnemosConfig):
    """list_wings returns all wing names."""
    palace = Palace(config)
    palace.ensure_structure()
    palace.create_wing("ProcureTrack")
    palace.create_wing("LightRAG")

    wings = palace.list_wings()
    assert set(wings) == {"ProcureTrack", "LightRAG"}


def test_list_drawers(config: MnemosConfig):
    """list_drawers returns all drawer files for a wing."""
    palace = Palace(config)
    palace.ensure_structure()
    palace.add_drawer("W1", "R1", "facts", "Fact one.", "", 0.5, [], "en")
    palace.add_drawer("W1", "R1", "decisions", "Decision one.", "", 0.7, [], "en")
    palace.add_drawer("W1", "R2", "facts", "Another fact.", "", 0.5, [], "en")

    drawers = palace.list_drawers(wing="W1")
    assert len(drawers) == 3


def test_recycle_drawer(config: MnemosConfig):
    """recycle_drawer moves file to _recycled/ with date prefix."""
    palace = Palace(config)
    palace.ensure_structure()
    drawer_path = palace.add_drawer("W1", "R1", "facts", "To delete.", "", 0.5, [], "en")

    assert drawer_path.exists()
    recycled_path = palace.recycle_drawer(drawer_path)

    assert not drawer_path.exists()
    assert recycled_path.exists()
    assert "_recycled" in str(recycled_path)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd C:/Projeler/mnemos && pytest tests/test_palace.py -v
```

Expected: FAIL — `mnemos.palace` does not exist.

- [ ] **Step 3: Implement mnemos/palace.py**

```python
"""Palace structure: Wing/Room/Hall CRUD operations."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from mnemos.config import MnemosConfig
from mnemos.obsidian import write_drawer_file, parse_drawer_file


class Palace:
    """Manages the palace directory structure inside an Obsidian vault."""

    def __init__(self, config: MnemosConfig) -> None:
        self.config = config

    def ensure_structure(self) -> None:
        """Create base palace directories if they don't exist."""
        self.config.wings_dir.mkdir(parents=True, exist_ok=True)
        self.config.identity_full_path.mkdir(parents=True, exist_ok=True)
        self.config.recycled_full_path.mkdir(parents=True, exist_ok=True)

    def create_wing(self, name: str) -> Path:
        """Create a wing directory with a _wing.md summary file."""
        wing_dir = self.config.wings_dir / name
        wing_dir.mkdir(parents=True, exist_ok=True)

        wing_md = wing_dir / "_wing.md"
        if not wing_md.exists():
            wing_md.write_text(
                f"---\nwing: {name}\ncreated: {date.today().isoformat()}\n---\n\n# {name}\n",
                encoding="utf-8",
            )
        return wing_dir

    def create_room(self, wing: str, room: str) -> Path:
        """Create a room directory with _room.md and hall subdirectories."""
        room_dir = self.config.wings_dir / wing / room
        room_dir.mkdir(parents=True, exist_ok=True)

        room_md = room_dir / "_room.md"
        if not room_md.exists():
            room_md.write_text(
                f"---\nwing: {wing}\nroom: {room}\ncreated: {date.today().isoformat()}\n---\n\n# {room}\n",
                encoding="utf-8",
            )

        for hall in self.config.halls:
            (room_dir / hall).mkdir(exist_ok=True)

        return room_dir

    def add_drawer(
        self,
        wing: str,
        room: str,
        hall: str,
        text: str,
        source: str,
        importance: float,
        entities: list[str],
        language: str,
    ) -> Path:
        """Add a drawer (memory note) to the palace.

        Creates wing/room/hall directories if needed.
        Returns the path to the created .md file.
        """
        self.create_wing(wing)
        self.create_room(wing, room)

        hall_dir = self.config.wings_dir / wing / room / hall
        hall_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        today = date.today().isoformat()
        slug = text[:40].lower()
        # Clean slug: keep only alphanumeric and spaces, replace spaces with dashes
        slug = "".join(c if c.isalnum() or c == " " else "" for c in slug)
        slug = slug.strip().replace(" ", "-")[:30]
        if not slug:
            slug = "memory"

        # Find unique name
        base_name = f"{today}-{slug}"
        filepath = hall_dir / f"{base_name}.md"
        counter = 1
        while filepath.exists():
            filepath = hall_dir / f"{base_name}-{counter}.md"
            counter += 1

        metadata = {
            "wing": wing,
            "room": room,
            "hall": hall,
            "source": source,
            "importance": importance,
            "entities": entities,
            "language": language,
        }
        write_drawer_file(filepath, metadata, text)
        return filepath

    def list_wings(self) -> list[str]:
        """Return names of all wings."""
        if not self.config.wings_dir.exists():
            return []
        return [d.name for d in self.config.wings_dir.iterdir() if d.is_dir()]

    def list_drawers(self, wing: str | None = None, room: str | None = None) -> list[Path]:
        """List all drawer .md files, optionally filtered by wing/room.

        Excludes _wing.md and _room.md summary files.
        """
        if wing:
            search_root = self.config.wings_dir / wing
            if room:
                search_root = search_root / room
        else:
            search_root = self.config.wings_dir

        if not search_root.exists():
            return []

        drawers = []
        for md_file in search_root.rglob("*.md"):
            if md_file.name.startswith("_"):
                continue
            drawers.append(md_file)
        return drawers

    def recycle_drawer(self, drawer_path: Path) -> Path:
        """Move a drawer to _recycled/ with a date prefix.

        Returns the new path in _recycled/.
        """
        self.config.recycled_full_path.mkdir(parents=True, exist_ok=True)

        today = date.today().isoformat()
        recycled_name = f"{today}_{drawer_path.name}"
        recycled_path = self.config.recycled_full_path / recycled_name

        # Handle name collision
        counter = 1
        while recycled_path.exists():
            recycled_path = self.config.recycled_full_path / f"{today}_{counter}_{drawer_path.name}"
            counter += 1

        drawer_path.rename(recycled_path)
        return recycled_path
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd C:/Projeler/mnemos && pytest tests/test_palace.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd C:/Projeler/mnemos
git add mnemos/palace.py tests/test_palace.py
git commit -m "feat: palace CRUD — wing/room/hall structure + recycle"
```

---

## Task 4: ChromaDB Search Engine

**Files:**
- Create: `mnemos/search.py`
- Create: `tests/test_search.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for mnemos.search."""

from pathlib import Path

import pytest

from mnemos.config import MnemosConfig
from mnemos.search import SearchEngine


@pytest.fixture
def engine(config: MnemosConfig) -> SearchEngine:
    """Create an in-memory SearchEngine for testing."""
    return SearchEngine(config, in_memory=True)


def test_index_and_search(engine: SearchEngine):
    """Index a drawer and find it via semantic search."""
    engine.index_drawer(
        drawer_id="test-001",
        text="Supabase RLS ile gitmeye karar verdik",
        metadata={"wing": "ProcureTrack", "room": "approval", "hall": "decisions"},
    )

    results = engine.search("Supabase kararları", limit=3)
    assert len(results) >= 1
    assert results[0]["drawer_id"] == "test-001"
    assert "Supabase" in results[0]["text"]


def test_search_with_wing_filter(engine: SearchEngine):
    """Metadata filter narrows results to a specific wing."""
    engine.index_drawer("d1", "Auth decision for project A", {"wing": "ProjectA", "hall": "decisions"})
    engine.index_drawer("d2", "Auth decision for project B", {"wing": "ProjectB", "hall": "decisions"})

    results = engine.search("auth decision", wing="ProjectA", limit=5)
    assert all(r["metadata"]["wing"] == "ProjectA" for r in results)


def test_search_with_hall_filter(engine: SearchEngine):
    """Hall filter restricts results to a memory type."""
    engine.index_drawer("d1", "We fixed the bug", {"wing": "W", "hall": "problems"})
    engine.index_drawer("d2", "We decided to use X", {"wing": "W", "hall": "decisions"})

    results = engine.search("something", wing="W", hall="problems", limit=5)
    assert all(r["metadata"]["hall"] == "problems" for r in results)


def test_delete_drawer(engine: SearchEngine):
    """Deleting a drawer removes it from the index."""
    engine.index_drawer("d1", "Some memory", {"wing": "W", "hall": "facts"})
    engine.delete_drawer("d1")

    results = engine.search("memory", limit=5)
    assert len(results) == 0


def test_get_stats(engine: SearchEngine):
    """Stats returns counts per wing."""
    engine.index_drawer("d1", "Memory one", {"wing": "A", "hall": "facts"})
    engine.index_drawer("d2", "Memory two", {"wing": "A", "hall": "decisions"})
    engine.index_drawer("d3", "Memory three", {"wing": "B", "hall": "facts"})

    stats = engine.get_stats()
    assert stats["total_drawers"] == 3
    assert stats["wings"]["A"] == 2
    assert stats["wings"]["B"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd C:/Projeler/mnemos && pytest tests/test_search.py -v
```

Expected: FAIL — `mnemos.search` does not exist.

- [ ] **Step 3: Implement mnemos/search.py**

```python
"""ChromaDB-based search engine with 3-layer strategy."""

from __future__ import annotations

from typing import Any

import chromadb

from mnemos.config import MnemosConfig


class SearchEngine:
    """Manages ChromaDB indexing and multi-layer search."""

    COLLECTION_NAME = "mnemos_drawers"

    def __init__(self, config: MnemosConfig, in_memory: bool = False) -> None:
        self.config = config
        if in_memory:
            self._client = chromadb.Client()
        else:
            path = str(config.chromadb_full_path)
            self._client = chromadb.PersistentClient(path=path)

        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def index_drawer(
        self,
        drawer_id: str,
        text: str,
        metadata: dict[str, Any],
    ) -> None:
        """Add or update a drawer in the ChromaDB index."""
        # ChromaDB metadata values must be str, int, float, or bool
        clean_meta = {}
        for k, v in metadata.items():
            if isinstance(v, (str, int, float, bool)):
                clean_meta[k] = v
            elif isinstance(v, list):
                clean_meta[k] = ",".join(str(item) for item in v)
            else:
                clean_meta[k] = str(v)

        self._collection.upsert(
            ids=[drawer_id],
            documents=[text],
            metadatas=[clean_meta],
        )

    def delete_drawer(self, drawer_id: str) -> None:
        """Remove a drawer from the index."""
        try:
            self._collection.delete(ids=[drawer_id])
        except Exception:
            pass  # Silently ignore if not found

    def search(
        self,
        query: str,
        wing: str | None = None,
        room: str | None = None,
        hall: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """3-layer search: metadata filter → semantic search → results.

        Layer 3 (re-ranking) is handled externally by the MCP server
        when an API key is available.
        """
        # Layer 1: Build metadata filter
        where_filter = self._build_where_filter(wing, room, hall)

        # Layer 2: Semantic search
        query_params: dict[str, Any] = {
            "query_texts": [query],
            "n_results": limit,
        }
        if where_filter:
            query_params["where"] = where_filter

        try:
            result = self._collection.query(**query_params)
        except Exception:
            return []

        # Format results
        results = []
        if result["ids"] and result["ids"][0]:
            for i, drawer_id in enumerate(result["ids"][0]):
                results.append({
                    "drawer_id": drawer_id,
                    "text": result["documents"][0][i] if result["documents"] else "",
                    "metadata": result["metadatas"][0][i] if result["metadatas"] else {},
                    "score": 1.0 - (result["distances"][0][i] if result["distances"] else 0),
                })
        return results

    def get_stats(self) -> dict[str, Any]:
        """Return collection statistics."""
        all_items = self._collection.get()
        total = len(all_items["ids"])

        wings: dict[str, int] = {}
        if all_items["metadatas"]:
            for meta in all_items["metadatas"]:
                wing = meta.get("wing", "unknown")
                wings[wing] = wings.get(wing, 0) + 1

        return {
            "total_drawers": total,
            "wings": wings,
        }

    def _build_where_filter(
        self,
        wing: str | None,
        room: str | None,
        hall: str | None,
    ) -> dict[str, Any] | None:
        """Build ChromaDB where filter from optional parameters."""
        conditions = []
        if wing:
            conditions.append({"wing": wing})
        if room:
            conditions.append({"room": room})
        if hall:
            conditions.append({"hall": hall})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd C:/Projeler/mnemos && pytest tests/test_search.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd C:/Projeler/mnemos
git add mnemos/search.py tests/test_search.py
git commit -m "feat: ChromaDB search engine with metadata filtering"
```

---

## Task 5: Knowledge Graph

**Files:**
- Create: `mnemos/graph.py`
- Create: `tests/test_graph.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for mnemos.graph."""

from mnemos.graph import KnowledgeGraph


def test_add_entity(tmp_path):
    """Add an entity and retrieve it."""
    db_path = tmp_path / "test.db"
    kg = KnowledgeGraph(db_path)

    kg.add_entity("ProcureTrack", "project")
    entity = kg.get_entity("ProcureTrack")

    assert entity is not None
    assert entity["name"] == "ProcureTrack"
    assert entity["type"] == "project"


def test_add_triple(tmp_path):
    """Add a triple and query it."""
    db_path = tmp_path / "test.db"
    kg = KnowledgeGraph(db_path)

    kg.add_triple("ProcureTrack", "uses", "Supabase", valid_from="2026-03-01")
    relations = kg.query_entity("ProcureTrack")

    assert len(relations) == 1
    assert relations[0]["predicate"] == "uses"
    assert relations[0]["object"] == "Supabase"


def test_temporal_query(tmp_path):
    """Temporal query returns only triples valid at given date."""
    db_path = tmp_path / "test.db"
    kg = KnowledgeGraph(db_path)

    kg.add_triple("Project", "uses", "OldTech", valid_from="2026-01-01", valid_to="2026-03-01")
    kg.add_triple("Project", "uses", "NewTech", valid_from="2026-03-01")

    # At Feb: only OldTech
    feb = kg.query_entity("Project", as_of="2026-02-15")
    assert len(feb) == 1
    assert feb[0]["object"] == "OldTech"

    # At April: only NewTech
    apr = kg.query_entity("Project", as_of="2026-04-01")
    assert len(apr) == 1
    assert apr[0]["object"] == "NewTech"


def test_timeline(tmp_path):
    """Timeline returns chronological events for an entity."""
    db_path = tmp_path / "test.db"
    kg = KnowledgeGraph(db_path)

    kg.add_triple("Proj", "started", "Init", valid_from="2026-01-01")
    kg.add_triple("Proj", "added", "Feature1", valid_from="2026-02-01")
    kg.add_triple("Proj", "added", "Feature2", valid_from="2026-03-01")

    timeline = kg.timeline("Proj")
    assert len(timeline) == 3
    assert timeline[0]["valid_from"] <= timeline[1]["valid_from"]


def test_delete_triples_by_source(tmp_path):
    """Deleting triples by source file removes only matching triples."""
    db_path = tmp_path / "test.db"
    kg = KnowledgeGraph(db_path)

    kg.add_triple("A", "r", "B", source_file="file1.md")
    kg.add_triple("A", "r", "C", source_file="file2.md")

    kg.delete_triples_by_source("file1.md")
    relations = kg.query_entity("A")
    assert len(relations) == 1
    assert relations[0]["object"] == "C"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd C:/Projeler/mnemos && pytest tests/test_graph.py -v
```

Expected: FAIL — `mnemos.graph` does not exist.

- [ ] **Step 3: Implement mnemos/graph.py**

```python
"""SQLite-based temporal knowledge graph."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class KnowledgeGraph:
    """Temporal triple store backed by SQLite."""

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL,
                properties TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS triples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object TEXT NOT NULL,
                valid_from TEXT,
                valid_to TEXT,
                confidence REAL DEFAULT 1.0,
                source_file TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_triples_subject ON triples(subject);
            CREATE INDEX IF NOT EXISTS idx_triples_object ON triples(object);
            CREATE INDEX IF NOT EXISTS idx_triples_source ON triples(source_file);
        """)
        self._conn.commit()

    def add_entity(self, name: str, entity_type: str, properties: dict | None = None) -> None:
        """Add or update an entity."""
        now = datetime.now(timezone.utc).isoformat()
        props = json.dumps(properties or {})
        self._conn.execute(
            """INSERT INTO entities (name, type, properties, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET type=?, properties=?, updated_at=?""",
            (name, entity_type, props, now, now, entity_type, props, now),
        )
        self._conn.commit()

    def get_entity(self, name: str) -> dict[str, Any] | None:
        """Get entity by name."""
        row = self._conn.execute(
            "SELECT name, type, properties, created_at FROM entities WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            return None
        return {
            "name": row["name"],
            "type": row["type"],
            "properties": json.loads(row["properties"]),
            "created_at": row["created_at"],
        }

    def add_triple(
        self,
        subject: str,
        predicate: str,
        obj: str,
        valid_from: str | None = None,
        valid_to: str | None = None,
        confidence: float = 1.0,
        source_file: str = "",
    ) -> None:
        """Add a temporal triple. Auto-creates entities if needed."""
        now = datetime.now(timezone.utc).isoformat()

        # Auto-create entities
        for entity_name in (subject, obj):
            self._conn.execute(
                """INSERT OR IGNORE INTO entities (name, type, properties, created_at, updated_at)
                   VALUES (?, 'unknown', '{}', ?, ?)""",
                (entity_name, now, now),
            )

        self._conn.execute(
            """INSERT INTO triples (subject, predicate, object, valid_from, valid_to,
               confidence, source_file, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (subject, predicate, obj, valid_from, valid_to, confidence, source_file, now),
        )
        self._conn.commit()

    def query_entity(
        self,
        entity: str,
        as_of: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query all current triples for an entity (as subject).

        If as_of is given, returns triples valid at that date.
        """
        if as_of:
            rows = self._conn.execute(
                """SELECT predicate, object, valid_from, valid_to, confidence, source_file
                   FROM triples
                   WHERE subject = ?
                     AND (valid_from IS NULL OR valid_from <= ?)
                     AND (valid_to IS NULL OR valid_to > ?)
                   ORDER BY valid_from""",
                (entity, as_of, as_of),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT predicate, object, valid_from, valid_to, confidence, source_file
                   FROM triples
                   WHERE subject = ? AND valid_to IS NULL
                   ORDER BY valid_from""",
                (entity,),
            ).fetchall()

        return [
            {
                "predicate": r["predicate"],
                "object": r["object"],
                "valid_from": r["valid_from"],
                "valid_to": r["valid_to"],
                "confidence": r["confidence"],
                "source_file": r["source_file"],
            }
            for r in rows
        ]

    def timeline(self, entity: str) -> list[dict[str, Any]]:
        """Get chronological history of an entity."""
        rows = self._conn.execute(
            """SELECT predicate, object, valid_from, valid_to, source_file
               FROM triples
               WHERE subject = ? AND valid_from IS NOT NULL
               ORDER BY valid_from ASC""",
            (entity,),
        ).fetchall()

        return [
            {
                "predicate": r["predicate"],
                "object": r["object"],
                "valid_from": r["valid_from"],
                "valid_to": r["valid_to"],
                "source_file": r["source_file"],
            }
            for r in rows
        ]

    def delete_triples_by_source(self, source_file: str) -> int:
        """Delete all triples from a given source file. Returns count deleted."""
        cursor = self._conn.execute(
            "DELETE FROM triples WHERE source_file = ?", (source_file,)
        )
        self._conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd C:/Projeler/mnemos && pytest tests/test_graph.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd C:/Projeler/mnemos
git add mnemos/graph.py tests/test_graph.py
git commit -m "feat: SQLite temporal knowledge graph"
```

---

## Task 6: Mining Engine (Regex + LLM Hybrid)

**Files:**
- Create: `mnemos/miner.py`
- Create: `mnemos/patterns/base.yaml`
- Create: `mnemos/patterns/tr.yaml`
- Create: `mnemos/patterns/en.yaml`
- Create: `tests/test_miner.py`

- [ ] **Step 1: Create language pattern files**

`mnemos/patterns/base.yaml`:
```yaml
# Language-independent patterns
dates:
  - "\\d{4}-\\d{2}-\\d{2}"                # ISO dates
  - "\\d{1,2}/\\d{1,2}/\\d{4}"            # DD/MM/YYYY
entities:
  wikilinks: "\\[\\[([^\\]]+)\\]\\]"      # [[wikilinks]]
  mentions: "@(\\w+)"                       # @mentions
```

`mnemos/patterns/tr.yaml`:
```yaml
decisions:
  - "karar verdik"
  - "karar aldik"
  - "karar aldık"
  - "ile gittik"
  - "ile gitmeye karar"
  - "secimini yaptik"
  - "tercih ettik"
  - "kullanmaya karar"
preferences:
  - "her zaman"
  - "asla yapma"
  - "tercihimiz"
  - "tercihim"
  - "daha iyi olur"
  - "kullaniyoruz"
problems:
  - "hata"
  - "sorun"
  - "bug"
  - "cozum"
  - "duzeltildi"
  - "calismadi"
  - "calismıyor"
  - "cozum olarak"
events:
  - "tamamlandi"
  - "tamamlandı"
  - "bitti"
  - "yayinlandi"
  - "basladik"
  - "gecildi"
  - "olusturuldu"
  - "eklendi"
```

`mnemos/patterns/en.yaml`:
```yaml
decisions:
  - "we decided"
  - "we chose"
  - "we picked"
  - "we went with"
  - "decision is"
  - "agreed to"
preferences:
  - "always use"
  - "never do"
  - "I prefer"
  - "we prefer"
  - "best practice"
problems:
  - "bug"
  - "error"
  - "broke"
  - "fixed"
  - "solution is"
  - "the fix"
  - "workaround"
events:
  - "shipped"
  - "completed"
  - "launched"
  - "deployed"
  - "it works"
  - "breakthrough"
  - "figured out"
  - "migrated"
```

- [ ] **Step 2: Write failing tests**

```python
"""Tests for mnemos.miner."""

from pathlib import Path

from mnemos.config import MnemosConfig
from mnemos.miner import Miner, detect_language, chunk_text, extract_entities_from_path


def test_detect_language_turkish():
    """Turkish text is detected correctly."""
    text = "Bugun approval flow uzerinde calistik. Karar verdik."
    assert detect_language(text) == "tr"


def test_detect_language_english():
    """English text is detected correctly."""
    text = "We decided to use Supabase for the auth system."
    assert detect_language(text) == "en"


def test_chunk_text():
    """Text is split into overlapping chunks."""
    text = "A" * 800 + "B" * 800 + "C" * 200
    chunks = chunk_text(text, chunk_size=800, overlap=100)
    assert len(chunks) >= 2
    assert len(chunks[0]) == 800
    # Overlap: end of chunk 0 should appear at start of chunk 1
    assert chunks[0][-100:] == chunks[1][:100]


def test_chunk_text_short():
    """Short text returns as single chunk."""
    text = "Short text."
    chunks = chunk_text(text, chunk_size=800, overlap=100)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_minimum():
    """Chunks below minimum size are discarded."""
    text = "Tiny"
    chunks = chunk_text(text, chunk_size=800, overlap=100, min_size=50)
    assert len(chunks) == 0


def test_extract_entities_from_path():
    """Wing name is extracted from file path."""
    path = Path("Sessions/2026-04-08-ProcureTrack-approval.md")
    entities = extract_entities_from_path(path)
    assert "ProcureTrack" in entities


def test_regex_mining_turkish(config: MnemosConfig, sample_session_tr: Path):
    """Miner extracts decisions and problems from Turkish text."""
    miner = Miner(config)
    extractions = miner.mine_file(sample_session_tr, use_llm=False)

    halls_found = {e["hall"] for e in extractions}
    assert "decisions" in halls_found or "preferences" in halls_found
    assert len(extractions) >= 1


def test_regex_mining_english(config: MnemosConfig, sample_session_en: Path):
    """Miner extracts decisions and problems from English text."""
    miner = Miner(config)
    extractions = miner.mine_file(sample_session_en, use_llm=False)

    halls_found = {e["hall"] for e in extractions}
    assert "decisions" in halls_found
    assert len(extractions) >= 1


def test_wing_assignment_from_frontmatter(config: MnemosConfig, sample_session_tr: Path):
    """Wing is assigned from frontmatter project field."""
    miner = Miner(config)
    extractions = miner.mine_file(sample_session_tr, use_llm=False)

    for e in extractions:
        assert e["wing"] == "ProcureTrack"
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd C:/Projeler/mnemos && pytest tests/test_miner.py -v
```

Expected: FAIL — `mnemos.miner` does not exist.

- [ ] **Step 4: Implement mnemos/miner.py**

```python
"""Hybrid mining engine: regex patterns + optional Claude API."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from mnemos.config import MnemosConfig
from mnemos.obsidian import parse_frontmatter


_PATTERNS_DIR = Path(__file__).parent / "patterns"

# Simple language detection: count Turkish-specific characters
_TR_CHARS = set("çğıöşüÇĞİÖŞÜ")
_TR_WORDS = {"ve", "ile", "bir", "icin", "için", "karar", "olan", "gibi", "daha", "bu", "su", "o"}


def detect_language(text: str) -> str:
    """Detect language of text. Returns 'tr' or 'en'."""
    words = text.lower().split()
    tr_score = sum(1 for w in words if w in _TR_WORDS)
    tr_score += sum(1 for c in text if c in _TR_CHARS)
    return "tr" if tr_score > len(words) * 0.05 else "en"


def chunk_text(
    text: str,
    chunk_size: int = 800,
    overlap: int = 100,
    min_size: int = 50,
) -> list[str]:
    """Split text into overlapping chunks."""
    if len(text) < min_size:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if len(chunk) >= min_size:
            chunks.append(chunk)
        start = end - overlap
        if start + min_size >= len(text):
            break
    return chunks


def extract_entities_from_path(filepath: Path) -> list[str]:
    """Extract potential entity names from file path.

    Looks for CamelCase or capitalized words in the filename.
    """
    stem = filepath.stem  # e.g. "2026-04-08-ProcureTrack-approval"
    # Find CamelCase words
    camel = re.findall(r"[A-Z][a-z]+(?:[A-Z][a-z]+)+", stem)
    # Find standalone capitalized words (3+ chars)
    caps = re.findall(r"\b([A-Z][a-z]{2,})\b", stem)
    return list(set(camel + caps))


def _load_patterns(language: str) -> dict[str, list[str]]:
    """Load regex patterns for a language."""
    pattern_file = _PATTERNS_DIR / f"{language}.yaml"
    if not pattern_file.exists():
        return {}
    with open(pattern_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class Miner:
    """Hybrid mining engine: regex + optional LLM."""

    def __init__(self, config: MnemosConfig) -> None:
        self.config = config
        self._patterns: dict[str, dict[str, list[str]]] = {}
        for lang in config.languages:
            self._patterns[lang] = _load_patterns(lang)

    def mine_file(
        self,
        filepath: Path,
        use_llm: bool = False,
    ) -> list[dict[str, Any]]:
        """Mine a single file for memories.

        Returns list of extraction dicts with keys:
        wing, room, hall, text, entities, language, source.
        """
        metadata, body = parse_frontmatter(filepath)
        if not body.strip():
            return []

        language = detect_language(body)
        wing = self._resolve_wing(metadata, filepath)
        room = self._resolve_room(metadata, body)

        # Extract entities
        entities = extract_entities_from_path(filepath)
        # Add entities from frontmatter
        if "project" in metadata:
            entities.append(metadata["project"])
        # Add entities from wikilinks
        wikilinks = re.findall(r"\[\[([^\]]+)\]\]", body)
        entities.extend(wikilinks)
        entities = list(set(entities))

        # Regex extraction
        extractions = self._regex_extract(body, language, wing, room, entities, filepath)

        # If no regex hits, chunk the whole body as facts
        if not extractions:
            chunks = chunk_text(body)
            for chunk in chunks:
                extractions.append({
                    "wing": wing,
                    "room": room,
                    "hall": "facts",
                    "text": chunk,
                    "entities": entities,
                    "language": language,
                    "source": str(filepath),
                })

        return extractions

    def _regex_extract(
        self,
        body: str,
        language: str,
        wing: str,
        room: str,
        entities: list[str],
        filepath: Path,
    ) -> list[dict[str, Any]]:
        """Extract memories using regex patterns."""
        patterns = self._patterns.get(language, {})
        extractions: list[dict[str, Any]] = []

        # Split body into paragraphs
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]

        for hall_type, pattern_list in patterns.items():
            for paragraph in paragraphs:
                paragraph_lower = paragraph.lower()
                for pattern in pattern_list:
                    if pattern.lower() in paragraph_lower:
                        extractions.append({
                            "wing": wing,
                            "room": room,
                            "hall": hall_type,
                            "text": paragraph,
                            "entities": entities,
                            "language": language,
                            "source": str(filepath),
                        })
                        break  # One match per paragraph per hall type is enough

        return extractions

    def _resolve_wing(self, metadata: dict[str, Any], filepath: Path) -> str:
        """Determine wing name from metadata or filepath."""
        # Try frontmatter project field
        if "project" in metadata:
            return metadata["project"]

        # Try extracting from filename
        entities = extract_entities_from_path(filepath)
        if entities:
            return entities[0]

        return "General"

    def _resolve_room(self, metadata: dict[str, Any], body: str) -> str:
        """Determine room name from metadata or content keywords."""
        # Try frontmatter tags
        tags = metadata.get("tags", [])
        if tags and isinstance(tags, list):
            return tags[0]

        # Simple keyword scoring for common rooms
        room_keywords = {
            "auth": ["auth", "login", "password", "session", "rls", "permission"],
            "api": ["api", "endpoint", "rest", "graphql", "request"],
            "database": ["database", "sql", "migration", "table", "schema"],
            "ui": ["ui", "frontend", "component", "page", "css", "layout"],
            "cost": ["cost", "price", "billing", "budget", "expense", "fatura"],
            "deployment": ["deploy", "ci", "cd", "docker", "pipeline"],
        }
        body_lower = body.lower()
        best_room = "general"
        best_score = 0
        for room_name, keywords in room_keywords.items():
            score = sum(1 for kw in keywords if kw in body_lower)
            if score > best_score:
                best_score = score
                best_room = room_name
        return best_room
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd C:/Projeler/mnemos && pytest tests/test_miner.py -v
```

Expected: All 9 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd C:/Projeler/mnemos
git add mnemos/miner.py mnemos/patterns/ tests/test_miner.py
git commit -m "feat: hybrid mining engine with TR/EN regex patterns"
```

---

## Task 7: File Watcher

**Files:**
- Create: `mnemos/watcher.py`
- Create: `tests/test_watcher.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for mnemos.watcher."""

import time
from pathlib import Path

from mnemos.config import MnemosConfig
from mnemos.watcher import VaultWatcher


def test_should_ignore(config: MnemosConfig):
    """Watcher ignores paths in the ignore list."""
    watcher = VaultWatcher(config, on_change=lambda *a: None)
    vault = config.vault_path

    assert watcher.should_ignore(vault / ".obsidian" / "config.json") is True
    assert watcher.should_ignore(vault / "Mnemos" / "_recycled" / "old.md") is True
    assert watcher.should_ignore(vault / "Templates" / "template.md") is True
    assert watcher.should_ignore(vault / "test.canvas") is True
    assert watcher.should_ignore(vault / "Sessions" / "log.md") is False
    assert watcher.should_ignore(vault / "Mnemos" / "Wings" / "P" / "test.md") is False


def test_should_ignore_non_md(config: MnemosConfig):
    """Watcher ignores non-markdown files."""
    watcher = VaultWatcher(config, on_change=lambda *a: None)
    vault = config.vault_path

    assert watcher.should_ignore(vault / "image.png") is True
    assert watcher.should_ignore(vault / "data.json") is True
    assert watcher.should_ignore(vault / "note.md") is False


def test_detect_changed_files(config: MnemosConfig):
    """Cold start detects files modified after last known state."""
    vault = config.vault_path

    # Create some files
    (vault / "Sessions" / "old.md").write_text("old content", encoding="utf-8")
    (vault / "Sessions" / "new.md").write_text("new content", encoding="utf-8")

    # Simulate mine_log with old.md already processed
    mine_log = {
        str(vault / "Sessions" / "old.md"): time.time() + 1  # future = already processed
    }

    watcher = VaultWatcher(config, on_change=lambda *a: None)
    changed = watcher.detect_changed_files(mine_log)

    paths = [str(p) for p in changed]
    assert str(vault / "Sessions" / "new.md") in paths
    # old.md was "processed" in the future, so it should NOT appear
    assert str(vault / "Sessions" / "old.md") not in paths
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd C:/Projeler/mnemos && pytest tests/test_watcher.py -v
```

Expected: FAIL — `mnemos.watcher` does not exist.

- [ ] **Step 3: Implement mnemos/watcher.py**

```python
"""File watcher: detect vault changes and trigger re-indexing."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any, Callable

from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer

from mnemos.config import MnemosConfig


# Event types
EVENT_CREATED = "created"
EVENT_MODIFIED = "modified"
EVENT_DELETED = "deleted"
EVENT_MOVED = "moved"

ChangeCallback = Callable[[str, Path, Path | None], None]
# callback(event_type, filepath, dest_path_for_moves)


class VaultWatcher:
    """Watches the Obsidian vault for file changes."""

    def __init__(self, config: MnemosConfig, on_change: ChangeCallback) -> None:
        self.config = config
        self._on_change = on_change
        self._observer: Observer | None = None

    def should_ignore(self, filepath: Path) -> bool:
        """Check if a file path should be ignored by the watcher."""
        # Only watch .md files
        if filepath.suffix != ".md":
            return True

        # Check against ignore patterns
        rel_path = str(filepath.relative_to(self.config.vault_path)).replace("\\", "/")
        for pattern in self.config.watcher_ignore:
            # Directory pattern (ends with /)
            if pattern.endswith("/"):
                dir_prefix = pattern.rstrip("/")
                if rel_path.startswith(dir_prefix + "/") or rel_path.startswith(dir_prefix):
                    return True
            # Glob pattern
            elif fnmatch.fnmatch(filepath.name, pattern):
                return True
            elif fnmatch.fnmatch(rel_path, pattern):
                return True

        return False

    def detect_changed_files(self, mine_log: dict[str, float]) -> list[Path]:
        """Find vault .md files that changed since last mine.

        mine_log maps filepath → last_processed_timestamp.
        Returns list of files that need re-mining.
        """
        changed = []
        vault = self.config.vault_path

        for md_file in vault.rglob("*.md"):
            if self.should_ignore(md_file):
                continue

            file_mtime = md_file.stat().st_mtime
            last_processed = mine_log.get(str(md_file), 0)

            if file_mtime > last_processed:
                changed.append(md_file)

        return changed

    def start(self) -> None:
        """Start watching the vault directory for changes."""
        if self._observer is not None:
            return

        handler = _VaultEventHandler(self)
        self._observer = Observer()
        self._observer.schedule(handler, str(self.config.vault_path), recursive=True)
        self._observer.daemon = True
        self._observer.start()

    def stop(self) -> None:
        """Stop watching."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None

    def _handle_event(self, event_type: str, filepath: Path, dest_path: Path | None = None) -> None:
        """Process a file system event after filtering."""
        if self.should_ignore(filepath):
            return
        if dest_path and self.should_ignore(dest_path):
            return
        self._on_change(event_type, filepath, dest_path)


class _VaultEventHandler(FileSystemEventHandler):
    """Watchdog event handler that delegates to VaultWatcher."""

    def __init__(self, watcher: VaultWatcher) -> None:
        self._watcher = watcher

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._handle_event(EVENT_CREATED, Path(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._handle_event(EVENT_MODIFIED, Path(event.src_path))

    def on_deleted(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._handle_event(EVENT_DELETED, Path(event.src_path))

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._handle_event(EVENT_MOVED, Path(event.src_path), Path(event.dest_path))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd C:/Projeler/mnemos && pytest tests/test_watcher.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd C:/Projeler/mnemos
git add mnemos/watcher.py tests/test_watcher.py
git commit -m "feat: vault file watcher with ignore patterns + cold start detection"
```

---

## Task 8: Memory Stack (L0-L3)

**Files:**
- Create: `mnemos/stack.py`
- Create: `tests/test_stack.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for mnemos.stack."""

from pathlib import Path

from mnemos.config import MnemosConfig
from mnemos.palace import Palace
from mnemos.stack import MemoryStack


def test_l0_identity(config: MnemosConfig):
    """L0 returns identity content."""
    palace = Palace(config)
    palace.ensure_structure()

    identity_file = config.identity_full_path / "L0-identity.md"
    identity_file.write_text(
        "---\nlevel: L0\n---\n\nTugra Demirors, GYP Energy, Windows 11\n",
        encoding="utf-8",
    )

    stack = MemoryStack(config)
    l0 = stack.recall(level="L0")

    assert "Tugra" in l0["content"]
    assert l0["level"] == "L0"
    assert l0["token_count"] > 0


def test_l1_wing_summaries(config: MnemosConfig):
    """L1 returns concatenated wing summaries."""
    palace = Palace(config)
    palace.ensure_structure()
    palace.create_wing("ProcureTrack")
    palace.create_wing("LightRAG")

    stack = MemoryStack(config)
    l1 = stack.recall(level="L1")

    assert "ProcureTrack" in l1["content"]
    assert "LightRAG" in l1["content"]
    assert l1["level"] == "L1"


def test_l2_wing_detail(config: MnemosConfig):
    """L2 returns room summaries for a specific wing."""
    palace = Palace(config)
    palace.ensure_structure()
    palace.create_wing("ProcureTrack")
    palace.create_room("ProcureTrack", "approval-flow")
    palace.create_room("ProcureTrack", "rfq-system")

    stack = MemoryStack(config)
    l2 = stack.recall(level="L2", wing="ProcureTrack")

    assert "approval-flow" in l2["content"]
    assert "rfq-system" in l2["content"]
    assert l2["level"] == "L2"


def test_wake_up(config: MnemosConfig):
    """wake_up returns combined L0 + L1 context."""
    palace = Palace(config)
    palace.ensure_structure()

    identity_file = config.identity_full_path / "L0-identity.md"
    identity_file.write_text(
        "---\nlevel: L0\n---\n\nTugra, GYP Energy\n",
        encoding="utf-8",
    )
    palace.create_wing("ProcureTrack")

    stack = MemoryStack(config)
    result = stack.wake_up()

    assert "Tugra" in result["identity"]
    assert "ProcureTrack" in result["wings_summary"]
    assert result["token_count"] > 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd C:/Projeler/mnemos && pytest tests/test_stack.py -v
```

Expected: FAIL — `mnemos.stack` does not exist.

- [ ] **Step 3: Implement mnemos/stack.py**

```python
"""L0-L3 memory stack for context loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mnemos.config import MnemosConfig
from mnemos.obsidian import parse_frontmatter


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English, ~3 for Turkish."""
    return max(1, len(text) // 4)


class MemoryStack:
    """Layered memory recall: L0 (identity) → L1 (summaries) → L2 (detail) → L3 (search)."""

    def __init__(self, config: MnemosConfig) -> None:
        self.config = config

    def recall(self, level: str = "L1", wing: str | None = None) -> dict[str, Any]:
        """Recall memory at the specified level.

        L0: Identity (~50 tokens)
        L1: All wing summaries (~150 tokens)
        L2: Room details for a specific wing (~300-500 tokens)
        L3: Handled by search engine, not here.
        """
        if level == "L0":
            content = self._load_l0()
        elif level == "L1":
            content = self._load_l1()
        elif level == "L2":
            if not wing:
                content = "[L2 requires a wing parameter]"
            else:
                content = self._load_l2(wing)
        else:
            content = f"[Unknown level: {level}]"

        return {
            "level": level,
            "content": content,
            "token_count": _estimate_tokens(content),
        }

    def wake_up(self) -> dict[str, Any]:
        """Session startup: load L0 + L1 combined."""
        identity = self._load_l0()
        wings_summary = self._load_l1()

        # Count pending sync (files in vault not yet in wings)
        combined = f"{identity}\n\n{wings_summary}"
        return {
            "identity": identity,
            "wings_summary": wings_summary,
            "token_count": _estimate_tokens(combined),
        }

    def _load_l0(self) -> str:
        """Load identity file."""
        identity_dir = self.config.identity_full_path
        identity_file = identity_dir / "L0-identity.md"
        if not identity_file.exists():
            return "[No identity configured. Run: mnemos init]"

        _, body = parse_frontmatter(identity_file)
        return body.strip()

    def _load_l1(self) -> str:
        """Load all _wing.md summaries."""
        wings_dir = self.config.wings_dir
        if not wings_dir.exists():
            return "[No wings found]"

        summaries = []
        for wing_dir in sorted(wings_dir.iterdir()):
            if not wing_dir.is_dir():
                continue
            wing_md = wing_dir / "_wing.md"
            if wing_md.exists():
                _, body = parse_frontmatter(wing_md)
                summaries.append(f"## {wing_dir.name}\n{body.strip()}")

        return "\n\n".join(summaries) if summaries else "[No wing summaries]"

    def _load_l2(self, wing: str) -> str:
        """Load room summaries for a specific wing."""
        wing_dir = self.config.wings_dir / wing
        if not wing_dir.exists():
            return f"[Wing '{wing}' not found]"

        summaries = []
        for room_dir in sorted(wing_dir.iterdir()):
            if not room_dir.is_dir():
                continue
            room_md = room_dir / "_room.md"
            if room_md.exists():
                _, body = parse_frontmatter(room_md)
                summaries.append(f"### {room_dir.name}\n{body.strip()}")

        return "\n\n".join(summaries) if summaries else f"[No rooms in wing '{wing}']"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd C:/Projeler/mnemos && pytest tests/test_stack.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd C:/Projeler/mnemos
git add mnemos/stack.py tests/test_stack.py
git commit -m "feat: L0-L3 memory stack with wake_up"
```

---

## Task 9: MCP Server (8 Tools)

**Files:**
- Create: `mnemos/server.py`
- Create: `mnemos/__main__.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for mnemos.server — tool logic (not MCP protocol)."""

from pathlib import Path

from mnemos.config import MnemosConfig
from mnemos.server import MnemosApp


def test_app_status(config: MnemosConfig):
    """mnemos_status returns valid stats."""
    app = MnemosApp(config, chromadb_in_memory=True)
    app.palace.ensure_structure()

    result = app.handle_status()
    assert "total_drawers" in result
    assert "vault_path" in result


def test_app_add_and_search(config: MnemosConfig):
    """Add a memory and search for it."""
    app = MnemosApp(config, chromadb_in_memory=True)
    app.palace.ensure_structure()

    add_result = app.handle_add(
        text="Supabase RLS ile gitmeye karar verdik",
        wing="ProcureTrack",
        room="approval-flow",
        hall="decisions",
        importance=0.8,
    )
    assert add_result["obsidian_path"] is not None

    search_results = app.handle_search(query="Supabase kararları", limit=3)
    assert len(search_results) >= 1
    assert "Supabase" in search_results[0]["text"]


def test_app_mine(config: MnemosConfig, sample_session_tr: Path):
    """Mine a session file and verify drawers are created."""
    app = MnemosApp(config, chromadb_in_memory=True)
    app.palace.ensure_structure()

    result = app.handle_mine(path=str(sample_session_tr), use_llm=False)
    assert result["files_scanned"] == 1
    assert result["drawers_created"] >= 1


def test_app_recall(config: MnemosConfig):
    """Recall L1 returns wing summaries."""
    app = MnemosApp(config, chromadb_in_memory=True)
    app.palace.ensure_structure()
    app.palace.create_wing("TestWing")

    result = app.handle_recall(level="L1")
    assert "TestWing" in result["content"]


def test_app_graph(config: MnemosConfig):
    """Graph query returns entity relations."""
    app = MnemosApp(config, chromadb_in_memory=True)
    app.palace.ensure_structure()

    app.graph.add_triple("ProcureTrack", "uses", "Supabase", valid_from="2026-03-01")
    result = app.handle_graph(entity="ProcureTrack")
    assert len(result["relations"]) == 1
    assert result["relations"][0]["object"] == "Supabase"


def test_app_timeline(config: MnemosConfig):
    """Timeline returns chronological events."""
    app = MnemosApp(config, chromadb_in_memory=True)
    app.palace.ensure_structure()

    app.graph.add_triple("Proj", "started", "Init", valid_from="2026-01-01")
    app.graph.add_triple("Proj", "added", "Feature", valid_from="2026-02-01")

    result = app.handle_timeline(entity="Proj")
    assert len(result) == 2


def test_app_wake_up(config: MnemosConfig):
    """Wake up returns identity + summary."""
    app = MnemosApp(config, chromadb_in_memory=True)
    app.palace.ensure_structure()
    app.palace.create_wing("TestWing")

    # Create identity
    identity_file = config.identity_full_path / "L0-identity.md"
    identity_file.write_text("---\nlevel: L0\n---\n\nTest User\n", encoding="utf-8")

    result = app.handle_wake_up()
    assert "Test User" in result["identity"]
    assert "TestWing" in result["wings_summary"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd C:/Projeler/mnemos && pytest tests/test_server.py -v
```

Expected: FAIL — `mnemos.server` does not exist.

- [ ] **Step 3: Implement mnemos/server.py**

```python
"""MCP server exposing 8 Mnemos tools."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from mnemos.config import MnemosConfig, load_config
from mnemos.graph import KnowledgeGraph
from mnemos.miner import Miner
from mnemos.obsidian import parse_drawer_file
from mnemos.palace import Palace
from mnemos.search import SearchEngine
from mnemos.stack import MemoryStack
from mnemos.watcher import VaultWatcher, EVENT_CREATED, EVENT_MODIFIED, EVENT_DELETED, EVENT_MOVED


class MnemosApp:
    """Core application logic for all 8 MCP tools."""

    def __init__(self, config: MnemosConfig, chromadb_in_memory: bool = False) -> None:
        self.config = config
        self.palace = Palace(config)
        self.search_engine = SearchEngine(config, in_memory=chromadb_in_memory)
        self.graph = KnowledgeGraph(config.graph_full_path)
        self.miner = Miner(config)
        self.stack = MemoryStack(config)
        self._mine_log = self._load_mine_log()

    # --- Tool handlers ---

    def handle_search(
        self,
        query: str,
        wing: str | None = None,
        room: str | None = None,
        hall: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        return self.search_engine.search(query, wing=wing, room=room, hall=hall, limit=limit)

    def handle_add(
        self,
        text: str,
        wing: str,
        room: str,
        hall: str = "facts",
        importance: float = 0.5,
    ) -> dict[str, Any]:
        drawer_path = self.palace.add_drawer(
            wing=wing, room=room, hall=hall, text=text,
            source="manual", importance=importance, entities=[], language="",
        )
        drawer_id = drawer_path.stem
        self.search_engine.index_drawer(
            drawer_id=drawer_id,
            text=text,
            metadata={"wing": wing, "room": room, "hall": hall, "importance": importance},
        )
        return {
            "drawer_id": drawer_id,
            "obsidian_path": str(drawer_path),
            "message": f"Memory added to {wing}/{room}/{hall}",
        }

    def handle_mine(
        self,
        path: str,
        mode: str = "auto",
        use_llm: bool = False,
    ) -> dict[str, Any]:
        target = Path(path)
        if not target.is_absolute():
            target = self.config.vault_path / target

        files_to_mine: list[Path] = []
        if target.is_file():
            files_to_mine = [target]
        elif target.is_dir():
            files_to_mine = list(target.rglob("*.md"))

        total_drawers = 0
        total_entities: set[str] = set()
        skipped = 0

        for filepath in files_to_mine:
            # Check mine log for dedup
            file_key = str(filepath)
            file_mtime = filepath.stat().st_mtime
            if self._mine_log.get(file_key, 0) >= file_mtime:
                skipped += 1
                continue

            extractions = self.miner.mine_file(filepath, use_llm=use_llm)

            for ext in extractions:
                drawer_path = self.palace.add_drawer(
                    wing=ext["wing"],
                    room=ext["room"],
                    hall=ext["hall"],
                    text=ext["text"],
                    source=str(filepath),
                    importance=0.5,
                    entities=ext["entities"],
                    language=ext["language"],
                )
                drawer_id = drawer_path.stem
                self.search_engine.index_drawer(
                    drawer_id=drawer_id,
                    text=ext["text"],
                    metadata={
                        "wing": ext["wing"],
                        "room": ext["room"],
                        "hall": ext["hall"],
                        "source": str(filepath),
                    },
                )
                total_entities.update(ext["entities"])

            total_drawers += len(extractions)
            self._mine_log[file_key] = time.time()

        self._save_mine_log()

        return {
            "files_scanned": len(files_to_mine) - skipped,
            "drawers_created": total_drawers,
            "entities_found": len(total_entities),
            "skipped": skipped,
        }

    def handle_status(self) -> dict[str, Any]:
        stats = self.search_engine.get_stats()
        stats["vault_path"] = str(self.config.vault_path)
        stats["wings_list"] = self.palace.list_wings()
        return stats

    def handle_recall(self, level: str = "L1", wing: str | None = None) -> dict[str, Any]:
        return self.stack.recall(level=level, wing=wing)

    def handle_graph(self, entity: str, as_of: str | None = None) -> dict[str, Any]:
        relations = self.graph.query_entity(entity, as_of=as_of)
        return {"entity": entity, "relations": relations}

    def handle_timeline(self, entity: str, from_date: str | None = None, to_date: str | None = None) -> list[dict]:
        timeline = self.graph.timeline(entity)
        if from_date:
            timeline = [t for t in timeline if t.get("valid_from", "") >= from_date]
        if to_date:
            timeline = [t for t in timeline if t.get("valid_from", "") <= to_date]
        return timeline

    def handle_wake_up(self) -> dict[str, Any]:
        return self.stack.wake_up()

    # --- Watcher callback ---

    def on_vault_change(self, event_type: str, filepath: Path, dest_path: Path | None = None) -> None:
        """Handle file system events from the watcher."""
        if event_type == EVENT_DELETED:
            drawer_id = filepath.stem
            self.search_engine.delete_drawer(drawer_id)
            self.graph.delete_triples_by_source(str(filepath))
        elif event_type in (EVENT_CREATED, EVENT_MODIFIED):
            self.handle_mine(path=str(filepath), use_llm=False)
        elif event_type == EVENT_MOVED and dest_path:
            # Delete old, index new
            old_id = filepath.stem
            self.search_engine.delete_drawer(old_id)
            self.graph.delete_triples_by_source(str(filepath))
            if dest_path.suffix == ".md":
                self.handle_mine(path=str(dest_path), use_llm=False)

    # --- Mine log persistence ---

    def _load_mine_log(self) -> dict[str, float]:
        log_path = self.config.mine_log_full_path
        if log_path.exists():
            return json.loads(log_path.read_text(encoding="utf-8"))
        return {}

    def _save_mine_log(self) -> None:
        log_path = self.config.mine_log_full_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(json.dumps(self._mine_log, indent=2), encoding="utf-8")


def create_mcp_server(config: MnemosConfig | None = None):
    """Create and configure the MCP server with all tools."""
    from mcp.server.fastmcp import FastMCP

    if config is None:
        config = load_config()

    app = MnemosApp(config)
    app.palace.ensure_structure()

    mcp = FastMCP("mnemos", instructions="Obsidian-native AI memory palace")

    @mcp.tool()
    def mnemos_search(
        query: str,
        wing: str = "",
        room: str = "",
        hall: str = "",
        limit: int = 5,
    ) -> str:
        """Search memories using semantic search with optional filters."""
        results = app.handle_search(
            query, wing=wing or None, room=room or None, hall=hall or None, limit=limit,
        )
        return json.dumps(results, ensure_ascii=False, indent=2)

    @mcp.tool()
    def mnemos_add(
        text: str,
        wing: str,
        room: str,
        hall: str = "facts",
        importance: float = 0.5,
    ) -> str:
        """Add a new memory to the palace."""
        result = app.handle_add(text=text, wing=wing, room=room, hall=hall, importance=importance)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool()
    def mnemos_mine(path: str = "", mode: str = "auto", use_llm: bool = False) -> str:
        """Mine files for memories. Path relative to vault root."""
        if not path:
            path = str(config.vault_path)
        result = app.handle_mine(path=path, mode=mode, use_llm=use_llm)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool()
    def mnemos_status() -> str:
        """Get palace status: drawer counts, wings, sync state."""
        result = app.handle_status()
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    def mnemos_recall(level: str = "L1", wing: str = "") -> str:
        """Recall memory at a specific level (L0/L1/L2)."""
        result = app.handle_recall(level=level, wing=wing or None)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    def mnemos_graph(entity: str, as_of: str = "") -> str:
        """Query entity relationships from the knowledge graph."""
        result = app.handle_graph(entity=entity, as_of=as_of or None)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    def mnemos_timeline(entity: str, from_date: str = "", to_date: str = "") -> str:
        """Get chronological history of an entity."""
        result = app.handle_timeline(entity=entity, from_date=from_date or None, to_date=to_date or None)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    def mnemos_wake_up() -> str:
        """Load session startup context (L0 identity + L1 wing summaries)."""
        result = app.handle_wake_up()
        return json.dumps(result, ensure_ascii=False, indent=2)

    # Start watcher if enabled
    if config.watcher_enabled:
        watcher = VaultWatcher(config, on_change=app.on_vault_change)
        # Cold start: process changed files
        changed = watcher.detect_changed_files(app._mine_log)
        for filepath in changed:
            app.handle_mine(path=str(filepath), use_llm=False)
        watcher.start()

    return mcp
```

- [ ] **Step 4: Create mnemos/__main__.py**

```python
"""Entry point for: python -m mnemos.server"""

from mnemos.server import create_mcp_server


def main():
    mcp = create_mcp_server()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd C:/Projeler/mnemos && pytest tests/test_server.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd C:/Projeler/mnemos
git add mnemos/server.py mnemos/__main__.py tests/test_server.py
git commit -m "feat: MCP server with 8 tools + watcher integration"
```

---

## Task 10: CLI (init / mine / search / status)

**Files:**
- Create: `mnemos/cli.py`

- [ ] **Step 1: Implement mnemos/cli.py**

```python
"""CLI entry point: mnemos init / mine / search / status."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mnemos.config import load_config, MnemosConfig, HALLS_DEFAULT, WATCHER_IGNORE_DEFAULT
from mnemos.server import MnemosApp

import yaml


def cmd_init(args: argparse.Namespace) -> None:
    """Interactive initialization wizard."""
    vault_path = args.vault or input("Obsidian vault path: ").strip()
    vault_path = Path(vault_path).resolve()

    if not vault_path.exists():
        print(f"Error: {vault_path} does not exist.")
        sys.exit(1)

    languages_input = input("Languages (comma-separated, e.g. tr,en) [en]: ").strip() or "en"
    languages = [lang.strip() for lang in languages_input.split(",")]

    config_data = {
        "version": 1,
        "vault": {"path": str(vault_path)},
        "palace": {
            "root": "Mnemos",
            "recycled": "Mnemos/_recycled",
            "identity": "Mnemos/Identity",
        },
        "mining": {
            "languages": languages,
            "use_llm": False,
            "sources": [
                {"path": "Sessions/", "mode": "sessions"},
                {"path": "Topics/", "mode": "general"},
                {"path": "Mnemos/Wings/", "mode": "skip"},
            ],
        },
        "search": {"default_limit": 5, "rerank": True},
        "watcher": {"enabled": True, "ignore": list(WATCHER_IGNORE_DEFAULT)},
        "halls": list(HALLS_DEFAULT),
        "storage": {
            "chromadb_path": "Mnemos/.chromadb",
            "graph_path": "Mnemos/.graph.db",
            "mine_log": "Mnemos/.mine_log.json",
        },
    }

    config_file = vault_path / "mnemos.yaml"
    config_file.write_text(yaml.dump(config_data, default_flow_style=False, allow_unicode=True), encoding="utf-8")
    print(f"Config written to {config_file}")

    # Create palace structure
    config = load_config(vault_path)
    app = MnemosApp(config)
    app.palace.ensure_structure()
    print("Palace structure created.")

    # Create identity placeholder
    identity_file = config.identity_full_path / "L0-identity.md"
    if not identity_file.exists():
        identity_file.write_text(
            "---\nlevel: L0\n---\n\n[Edit this file to describe yourself]\n",
            encoding="utf-8",
        )
        print(f"Identity file created: {identity_file}")

    # Offer to mine existing files
    mine_now = input("Mine existing vault files now? [Y/n]: ").strip().lower()
    if mine_now != "n":
        result = app.handle_mine(path=str(vault_path), use_llm=False)
        print(f"Mined {result['files_scanned']} files, created {result['drawers_created']} memories.")

    print("\nDone! Connect to Claude Code with:")
    print(f'  claude mcp add mnemos -- python -m mnemos.server --vault "{vault_path}"')


def cmd_mine(args: argparse.Namespace) -> None:
    """Mine files for memories."""
    config = load_config(args.vault)
    app = MnemosApp(config)
    app.palace.ensure_structure()

    path = args.path or str(config.vault_path)
    result = app.handle_mine(path=path, use_llm=args.llm)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_search(args: argparse.Namespace) -> None:
    """Search memories."""
    config = load_config(args.vault)
    app = MnemosApp(config)

    results = app.handle_search(
        query=args.query,
        wing=args.wing,
        hall=args.hall,
        limit=args.limit,
    )
    for r in results:
        print(f"[{r.get('metadata', {}).get('wing', '?')}/{r.get('metadata', {}).get('hall', '?')}] "
              f"(score: {r.get('score', 0):.2f})")
        print(f"  {r['text'][:120]}...")
        print()


def cmd_status(args: argparse.Namespace) -> None:
    """Show palace status."""
    config = load_config(args.vault)
    app = MnemosApp(config)

    result = app.handle_status()
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(prog="mnemos", description="Obsidian-native AI memory palace")
    parser.add_argument("--vault", type=str, default=None, help="Path to Obsidian vault")

    subparsers = parser.add_subparsers(dest="command")

    # init
    init_parser = subparsers.add_parser("init", help="Initialize Mnemos in a vault")
    init_parser.set_defaults(func=cmd_init)

    # mine
    mine_parser = subparsers.add_parser("mine", help="Mine files for memories")
    mine_parser.add_argument("path", nargs="?", default=None, help="File or directory to mine")
    mine_parser.add_argument("--llm", action="store_true", help="Use Claude API for mining")
    mine_parser.set_defaults(func=cmd_mine)

    # search
    search_parser = subparsers.add_parser("search", help="Search memories")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--wing", default=None, help="Filter by wing")
    search_parser.add_argument("--hall", default=None, help="Filter by hall type")
    search_parser.add_argument("--limit", type=int, default=5, help="Max results")
    search_parser.set_defaults(func=cmd_search)

    # status
    status_parser = subparsers.add_parser("status", help="Show palace status")
    status_parser.set_defaults(func=cmd_status)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test CLI manually**

```bash
cd C:/Projeler/mnemos && pip install -e . && mnemos --help && mnemos status --vault /tmp/test_vault 2>&1 || true
```

Expected: Help text appears. Status may error (no vault) — that's OK for now.

- [ ] **Step 3: Commit**

```bash
cd C:/Projeler/mnemos
git add mnemos/cli.py
git commit -m "feat: CLI commands — init, mine, search, status"
```

---

## Task 11: Integration Test + End-to-End Verification

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
"""End-to-end integration test: mine → search → graph → recall."""

from pathlib import Path

from mnemos.config import MnemosConfig
from mnemos.server import MnemosApp


def test_full_cycle(config: MnemosConfig, sample_session_tr: Path, sample_session_en: Path, sample_topic: Path):
    """Full cycle: mine files → search → verify graph → recall."""
    app = MnemosApp(config, chromadb_in_memory=True)
    app.palace.ensure_structure()

    # Step 1: Mine all fixture files
    for filepath in [sample_session_tr, sample_session_en, sample_topic]:
        result = app.handle_mine(path=str(filepath), use_llm=False)
        assert result["drawers_created"] >= 1, f"No drawers from {filepath.name}"

    # Step 2: Search should find relevant results
    results = app.handle_search(query="Supabase karar", limit=5)
    assert len(results) >= 1
    assert any("Supabase" in r["text"] or "supabase" in r["text"].lower() for r in results)

    # Step 3: Search with wing filter
    results_filtered = app.handle_search(query="cost problem", wing="LightRAG", limit=5)
    assert all(r["metadata"].get("wing") == "LightRAG" for r in results_filtered)

    # Step 4: Status should show multiple wings
    status = app.handle_status()
    assert status["total_drawers"] >= 3

    # Step 5: Recall L1 should list wings
    l1 = app.handle_recall(level="L1")
    assert l1["token_count"] > 0

    # Step 6: Palace structure should exist on disk
    wings = app.palace.list_wings()
    assert len(wings) >= 1

    # Step 7: Re-mine should skip already processed files
    result2 = app.handle_mine(path=str(sample_session_tr), use_llm=False)
    assert result2["skipped"] == 1


def test_recycle_removes_from_index(config: MnemosConfig):
    """Recycling a drawer removes it from search index."""
    app = MnemosApp(config, chromadb_in_memory=True)
    app.palace.ensure_structure()

    # Add a memory
    add_result = app.handle_add(
        text="This memory will be recycled",
        wing="TestWing",
        room="test-room",
        hall="facts",
    )
    drawer_path = Path(add_result["obsidian_path"])

    # Verify it's searchable
    results = app.handle_search(query="recycled memory", limit=3)
    assert len(results) >= 1

    # Recycle it
    app.palace.recycle_drawer(drawer_path)
    drawer_id = drawer_path.stem
    app.search_engine.delete_drawer(drawer_id)

    # Verify it's gone from search
    results_after = app.handle_search(query="recycled memory", limit=3)
    found = [r for r in results_after if r["drawer_id"] == drawer_id]
    assert len(found) == 0
```

- [ ] **Step 2: Run all tests**

```bash
cd C:/Projeler/mnemos && pytest tests/ -v
```

Expected: ALL tests PASS.

- [ ] **Step 3: Commit**

```bash
cd C:/Projeler/mnemos
git add tests/test_integration.py
git commit -m "test: end-to-end integration tests — mine, search, recycle"
```

---

## Task 12: README + Final Polish

**Files:**
- Create: `README.md`
- Create: `.gitignore`

- [ ] **Step 1: Create .gitignore**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.eggs/

# Testing
.pytest_cache/
.coverage
htmlcov/

# IDE
.vscode/
.idea/

# Mnemos runtime data (in vault, not in repo)
.chromadb/
*.db
.mine_log.json

# Secrets
*.env
.env*
*credentials*
```

- [ ] **Step 2: Create README.md**

```markdown
# Mnemos

**Obsidian-native AI memory palace with semantic search.**

Your AI's memory lives in your Obsidian vault. Human-readable. Searchable. Yours.

Inspired by [MemPalace](https://github.com/MemPalace/mempalace) — rebuilt from scratch for Obsidian.

## Why Mnemos?

| | MemPalace | Mnemos |
|--|-----------|--------|
| **Storage** | ChromaDB binary (opaque) | Obsidian markdown (you can read it) |
| **Mining** | English regex only | Hybrid: regex + Claude API (any language) |
| **Access** | AI only | You AND your AI |
| **Search** | Semantic | Semantic + metadata + optional re-rank |
| **Deletion** | API call | Delete in Obsidian, or move to recycle |
| **Ecosystem** | Standalone | Obsidian Graph View, Dataview, plugins |

## Quick Start

```bash
pip install mnemos
mnemos init
claude mcp add mnemos -- python -m mnemos.server
```

## How It Works

Mnemos uses a **Memory Palace** architecture inspired by the ancient Greek technique:

```
Your Obsidian Vault
  +-- Mnemos/
      +-- Wings/           (projects & people)
      |   +-- ProjectA/
      |   |   +-- auth/        (topic rooms)
      |   |   |   +-- decisions/   (memory types)
      |   |   |   +-- facts/
      |   |   |   +-- problems/
      |   +-- ProjectB/
      +-- Identity/        (who you are)
      +-- _recycled/       (soft-deleted memories)
```

Every memory is a markdown file you can read and edit. ChromaDB runs alongside for fast semantic search.

## MCP Tools

| Tool | Description |
|------|-------------|
| `mnemos_search` | Semantic search with wing/room/hall filters |
| `mnemos_add` | Add a new memory |
| `mnemos_mine` | Extract memories from files |
| `mnemos_status` | Palace statistics |
| `mnemos_recall` | Load context (L0 identity, L1 summaries, L2 details) |
| `mnemos_graph` | Query entity relationships |
| `mnemos_timeline` | Chronological entity history |
| `mnemos_wake_up` | Session startup context |

## Mining

Mnemos extracts memories using a hybrid approach:

1. **Regex patterns** — detects decisions, problems, events, preferences in Turkish and English
2. **Claude API** (optional) — catches what regex misses, works in any language

```bash
# Mine your vault
mnemos mine Sessions/

# With Claude API for better quality
pip install mnemos[llm]
mnemos mine Sessions/ --llm
```

## File Watcher

Changes you make in Obsidian are automatically synced:

- **Add** a note → indexed in ChromaDB
- **Edit** a note → re-indexed
- **Delete** a note → removed from index
- **Move** a note → metadata updated

## Configuration

`mnemos.yaml` in your vault root:

```yaml
version: 1
vault:
  path: "/path/to/your/vault"
mining:
  languages: [tr, en]
  use_llm: false
halls:
  - decisions
  - facts
  - events
  - preferences
  - problems
```

## License

MIT — built from scratch, inspired by [MemPalace](https://github.com/MemPalace/mempalace).
```

- [ ] **Step 3: Run full test suite one final time**

```bash
cd C:/Projeler/mnemos && pytest tests/ -v --tb=short
```

Expected: ALL tests PASS.

- [ ] **Step 4: Commit**

```bash
cd C:/Projeler/mnemos
git add README.md .gitignore
git commit -m "docs: README + .gitignore"
```

- [ ] **Step 5: Verify final project structure**

```bash
cd C:/Projeler/mnemos && find . -type f -not -path './.git/*' | sort
```

Expected output should match the file map from the spec.

---

## Summary

| Task | Component | Tests |
|------|-----------|-------|
| 1 | Scaffolding + Config | 3 |
| 2 | Obsidian I/O | 4 |
| 3 | Palace CRUD | 7 |
| 4 | ChromaDB Search | 5 |
| 5 | Knowledge Graph | 5 |
| 6 | Mining Engine | 9 |
| 7 | File Watcher | 3 |
| 8 | Memory Stack | 4 |
| 9 | MCP Server | 7 |
| 10 | CLI | manual |
| 11 | Integration | 2 |
| 12 | README + Polish | - |
| **Total** | **12 tasks** | **~49 tests** |
