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
mnemos mine Sessions/
pip install mnemos[llm]
mnemos mine Sessions/ --llm
```

## File Watcher

Changes you make in Obsidian are automatically synced:
- **Add** a note -> indexed in ChromaDB
- **Edit** a note -> re-indexed
- **Delete** a note -> removed from index
- **Move** a note -> metadata updated

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
