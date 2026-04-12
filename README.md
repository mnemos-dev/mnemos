<h1 align="center">Mnemos</h1>
<p align="center"><strong>Obsidian-native AI memory palace with semantic search</strong></p>
<p align="center">Your AI's memory lives in your Obsidian vault. Human-readable. Searchable. Yours.</p>
<p align="center">
  <a href="https://github.com/mnemos-dev/mnemos/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License">
  </a>
  <a href="https://www.python.org/downloads/">
    <img src="https://img.shields.io/badge/python-3.10+-green.svg" alt="Python 3.10+">
  </a>
  <a href="https://github.com/MemPalace/mempalace">
    <img src="https://img.shields.io/badge/inspired%20by-MemPalace-purple.svg" alt="Inspired by MemPalace">
  </a>
</p>

---

## Why Mnemos?

[MemPalace](https://github.com/MemPalace/mempalace) proved that structured memory architecture works for AI. Mnemos takes the same idea and makes it **Obsidian-native** — your memories are markdown files you can read, edit, and organize.

| | MemPalace | Mnemos |
|--|-----------|--------|
| **Storage** | ChromaDB binary (opaque) | Obsidian markdown (you can read it) |
| **Mining** | English regex only | Hybrid: regex + Claude API (any language) |
| **Access** | AI only | You AND your AI |
| **Search** | Semantic | Semantic + metadata + optional re-rank |
| **Deletion** | API call | Delete in Obsidian, auto-synced |
| **Ecosystem** | Standalone | Obsidian Graph View, Dataview, plugins |

## Quick Start

```bash
# Install
pip install mnemos-dev

# Initialize your vault
mnemos init

# Connect to Claude Code
claude mcp add mnemos -- python -m mnemos --vault /path/to/your/vault
```

## How It Works

Mnemos uses a **Memory Palace** architecture inspired by the ancient Greek *method of loci*:

```
Your Obsidian Vault
  +-- Mnemos/
      +-- Wings/              (projects & people)
      |   +-- ProjectA/
      |   |   +-- auth/           (topic rooms)
      |   |   |   +-- decisions/      (memory types)
      |   |   |   +-- facts/
      |   |   |   +-- problems/
      |   +-- ProjectB/
      +-- Identity/           (who you are - L0)
      +-- _recycled/          (soft-deleted memories)
```

Every memory is a `.md` file with YAML frontmatter. ChromaDB runs alongside as a vector index for fast semantic search. **Obsidian is the master, ChromaDB is the index** — if it's not in your vault, it doesn't exist.

## MCP Tools

Mnemos exposes 8 tools via [Model Context Protocol](https://modelcontextprotocol.io/):

| Tool | Description |
|------|-------------|
| `mnemos_search` | Semantic search with wing/room/hall filters |
| `mnemos_add` | Add a new memory |
| `mnemos_mine` | Extract memories from files or directories |
| `mnemos_status` | Palace statistics |
| `mnemos_recall` | Load context (L0 identity, L1 summaries, L2 details) |
| `mnemos_graph` | Query entity relationships |
| `mnemos_timeline` | Chronological entity history |
| `mnemos_wake_up` | Session startup context (~200 tokens) |

Works with **Claude Code**, **Cursor**, **ChatGPT**, and any MCP-compatible client.

## Mining

Mnemos extracts memories using a hybrid approach:

1. **Regex patterns** — detects decisions, problems, events, preferences in Turkish and English
2. **Claude API** (optional) — catches what regex misses, works in any language

```bash
# Mine your session notes
mnemos mine Sessions/

# Use Claude API for better extraction
pip install mnemos[llm]
mnemos mine Sessions/ --llm
```

### External Sources (Read-Only)

Mine data from outside your vault without modifying the source:

```bash
# Mine Claude Code memory (one-shot, read-only)
mnemos mine ~/.claude/projects/my-project/memory --external
```

External sources are mined once to extract memories into your palace. The source files are **never modified or watched**.

## File Watcher

Changes you make in Obsidian are automatically synced to ChromaDB:

| Action | Result |
|--------|--------|
| **Add** a note | Indexed in ChromaDB |
| **Edit** a note | Re-indexed |
| **Delete** a note | Removed from index |
| **Move** a note | Metadata updated |

The watcher runs inside the MCP server. When the server restarts, it detects any changes made while it was offline.

## Memory Stack (L0-L3)

Efficient context loading — your AI knows you without wasting tokens:

| Level | Content | Tokens | Loaded |
|-------|---------|--------|--------|
| L0 | Identity | ~50 | Every session |
| L1 | Wing summaries | ~150 | Every session |
| L2 | Room details | ~300-500 | When topic mentioned |
| L3 | Deep search | ~200-400 | When asked |

## Configuration

`mnemos.yaml` in your vault root:

```yaml
version: 1
vault:
  path: "/path/to/your/vault"
mining:
  languages: [tr, en]
  use_llm: false
  sources:
    - path: "Sessions/"
      mode: sessions
    - path: "Topics/"
      mode: general
halls:
  - decisions
  - facts
  - events
  - preferences
  - problems
```

## Architecture

```
Claude Code / Cursor / ChatGPT
        |
        | MCP (stdio)
        v
  +------------------+
  |  Mnemos Server   |
  |  (8 MCP tools)   |
  +-----|------|------+
        |      |
   ChromaDB   SQLite
   (vectors)  (knowledge graph)
        |      |
        v      v
  +-----------------------+
  |   Obsidian Vault      |
  |   (.md files = truth) |
  +-----------------------+
```

## Contributing

Contributions welcome! This project is built from scratch (not a fork) — inspired by [MemPalace](https://github.com/MemPalace/mempalace)'s palace architecture.

```bash
git clone https://github.com/mnemos-dev/mnemos.git
cd mnemos
pip install -e ".[dev,llm]"
pytest tests/ -v
```

## License

MIT — Copyright 2026 Tugra Demirors / GYP Energy
