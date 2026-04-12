# Mnemos — Obsidian-Native AI Memory Palace

**Date:** 2026-04-12
**Author:** Tuğra Demirors (GYP Energy)
**Status:** Approved
**Inspired by:** [MemPalace](https://github.com/MemPalace/mempalace) (MIT License)

---

## 1. Overview

Mnemos is an open-source, Obsidian-native AI memory system that stores memories as human-readable markdown files while providing semantic search via ChromaDB. It combines MemPalace's palace architecture with LLM-powered mining and Obsidian's ecosystem.

### Key Differentiators vs MemPalace

| Aspect | MemPalace | Mnemos |
|--------|-----------|--------|
| Storage | ChromaDB binary (opaque) | Obsidian .md (human-readable) |
| Mining | English-only regex | Hybrid: regex + Claude API (any language) |
| Access | AI-only | Dual: human + AI |
| Deletion | API call | Obsidian file ops → auto-sync |
| Ecosystem | Standalone | Obsidian plugins, Graph View, Dataview |

### Design Principles

1. **Obsidian is master, ChromaDB is index** — every memory exists as a .md file first
2. **Works without API key** — regex-only mode is functional, LLM enhances quality
3. **Dual access** — users can read, edit, delete memories via Obsidian; AI via MCP
4. **Watcher-based sync** — any vault change is automatically reflected in ChromaDB

---

## 2. Palace Architecture (Data Model)

### Hierarchy

```
Palace (vault root)
├── Wing (person or project)
│   ├���─ Room (topic/area)
│   │   ├── Hall (memory type)
│   │   │   ├── Closet (summary — L1 cache)
│   │   │   └── Drawer (original text chunk)
```

### Obsidian Mapping

```
<vault>/
├── Sessions/                    ← existing, untouched
├── Topics/                      ← existing, untouched
├── Mnemos/
│   ├── Wings/
│   │   ├── <ProjectName>/
│   │   │   ├── _wing.md          ← wing summary + metadata
│   │   │   ├── <room-name>/
│   │   │   ���   ├── _room.md      ← room summary
│   │   │   │   ├── decisions/
│   │   │   │   │   └── <date>-<slug>.md
│   │   │   │   ├── facts/
│   │   │   │   ├── events/
│   │   │   │   ├─�� preferences/
│   │   ���   │   └── problems/
│   │   │   └── <room-name>/
│   │   └── <ProjectName>/
│   ├── Identity/
│   │   └── L0-identity.md        ← who you are (~50 tokens)
│   ├── _recycled/                ← soft-deleted memories
│   ├── .chromadb/                ← vector index (hidden)
��   ├── .graph.db                 ← SQLite knowledge graph (hidden)
│   └── .mine_log.json            ← mining state tracker (hidden)
```

### Hall Types (Fixed)

| Hall | Content | Examples |
|------|---------|----------|
| `decisions` | Decisions made | "We chose Supabase RLS for row-level auth" |
| `facts` | Technical facts | "ProcureTrack uses Next.js 14 + Supabase" |
| `events` | Milestones/events | "Kanban auto-advance fix completed" |
| `preferences` | User preferences | "Turkish commit messages, git auto-push" |
| `problems` | Problems/solutions | "Google Gemini cost 1125 TL, switched to Anthropic" |

### Drawer Format (Single Memory Note)

```markdown
---
wing: ProcureTrack
room: approval-flow
hall: decisions
source: Sessions/2026-04-08-ProcureTrack-approval.md
mined_at: 2026-04-12T15:30:00
importance: 0.8
entities: [ProcureTrack, Supabase, RLS]
language: tr
---

Approval flow icin Supabase RLS policy kullanmaya karar verdik.
Her kullanici sadece kendi departmaninin PO'larini gorebilecek.
Manager rolu tum departmanlari gorebilir.
```

### ChromaDB Entry (Mirror)

```python
{
    "id": "procuretrack-approval-flow-decisions-2026-04-08-001",
    "text": "Approval flow icin Supabase RLS policy...",
    "metadata": {
        "wing": "ProcureTrack",
        "room": "approval-flow",
        "hall": "decisions",
        "source": "Sessions/2026-04-08-...",
        "importance": 0.8,
        "language": "tr"
    }
}
```

---

## 3. Watcher (Bidirectional Sync)

### Mechanism

The watcher uses Python's `watchdog` library to monitor the vault directory. It runs inside the MCP server process.

### Event Handling

| Vault Event | Mnemos Response |
|-------------|----------------|
| New .md file created | Mine → chunk → index in ChromaDB + graph |
| Existing .md modified | Delete old index → re-mine → re-index |
| .md file deleted | Remove from ChromaDB + graph |
| .md file moved | Update wing/room metadata in ChromaDB + graph |

### Ignored Paths

- `.obsidian/`
- `Mnemos/_recycled/`
- `Mnemos/.chromadb/`
- `Templates/`
- `*.canvas`

### Cold Start Recovery

When the MCP server starts, it compares `mtime` of all vault files against `.mine_log.json`. Any files modified while the server was stopped are re-mined automatically.

---

## 4. Deletion: Soft Delete with _recycled

### When AI calls `mnemos_forget`:

1. Remove from ChromaDB index
2. Remove related triples from knowledge graph
3. Move Obsidian .md to `Mnemos/_recycled/` with date prefix: `2026-04-12_original-name.md`
4. **Never delete the .md file** — only user can permanently delete from `_recycled/`

### When user deletes from Obsidian:

1. Watcher detects file removal
2. Remove from ChromaDB + graph
3. File is already gone (user chose to delete it)

### Recovery:

Move file from `_recycled/` back to `Wings/` → watcher picks it up → re-indexes automatically.

---

## 5. Search Engine (3-Layer Strategy)

```
Query received
    │
    ├── Layer 1: Metadata filter (free, <10ms)
    │   WHERE wing="X" AND hall="Y"
    │   Narrows 500 drawers → ~12
    │
    ├── Layer 2: ChromaDB semantic search (free, <50ms)
    │   Cosine similarity on query vector
    │   Returns top-K results
    │
    └── Layer 3: Claude re-ranking (optional, ~$0.01/query, ~1s)
        Send top-K to Claude: "rank by relevance"
        Returns final ordered results
```

| Layer | Cost | Speed | Quality | When |
|-------|------|-------|---------|------|
| 1 — Metadata | $0 | <10ms | Coarse filter | Always |
| 2 — Semantic | $0 | <50ms | Good | Always |
| 3 — Re-rank | ~$0.01 | ~1s | Excellent | If API key exists |

Users without API key get Layer 1+2 (good enough). With key, Layer 3 adds precision.

---

## 6. Mining Engine (Hybrid)

### Pipeline

```
Input: .md file
    │
    ├── Step 1: Read file, detect language (tr/en)
    │
    ├── Step 2: Regex/keyword extraction
    │   Language-specific patterns from patterns/<lang>.yaml
    │   - Decisions: "karar verdik", "we decided", "chose"
    │   - Preferences: "tercih", "always use", "I prefer"
    │   - Events: "tamamlandi", "shipped", "completed"
    │   - Problems: "hata", "bug", "sorun", "fixed"
    │   - Dates: ISO, relative ("gecen hafta" → absolute)
    │   - Entities: title, @mentions, [[wikilinks]]
    │
    ├── Step 3: Claude API (if key available)
    │   For text that regex missed:
    │   "Extract decisions, problems, preferences from this text"
    │   Model: claude-sonnet-4-6 (cost-effective)
    │
    ├── Step 4: Wing/Room assignment
    │   - Wing: from file path or entity detection
    │   - Room: keyword scoring on content
    │   - Hall: from extraction type
    │
    └── Step 5: Persist
        → Write Obsidian .md (Wings/ folder)
        → Index in ChromaDB
        → Add entities to knowledge graph
```

### Chunking Strategy

- Chunk size: 800 characters with 100 character overlap
- Minimum chunk: 50 characters (skip smaller)
- One drawer per chunk

### Deduplication

- Track `source_file + mtime` in `.mine_log.json`
- Skip files that haven't changed since last mine
- `mnemos mine --rebuild` forces full re-mine

### Language Patterns

Stored in `mnemos/patterns/<lang>.yaml`:

```yaml
# patterns/tr.yaml
decisions:
  - "karar verdik"
  - "karar aldik"
  - "ile gittik"
  - "secimini yaptik"
  - "tercih ettik"
preferences:
  - "her zaman"
  - "asla yapma"
  - "tercihim"
  - "daha iyi olur"
problems:
  - "hata"
  - "sorun"
  - "bug"
  - "cozum"
  - "duzeltildi"
events:
  - "tamamlandi"
  - "bitti"
  - "yayinlandi"
  - "basladik"
  - "gecildi"
```

---

## 7. Memory Stack (L0-L3)

### Layers

| Level | Content | Tokens | Loaded |
|-------|---------|--------|--------|
| L0 | Identity | ~50 | Always (wake_up) |
| L1 | Wing summaries (critical facts) | ~150 | Always (wake_up) |
| L2 | Room details for a specific wing | ~300-500 | On topic mention |
| L3 | Deep search results | ~200-400/query | On specific question |

### Trigger Flow

```
Session starts → mnemos_wake_up()
  → L0: read Identity/L0-identity.md
  → L1: read each wing's _wing.md summary
  → Total: ~200 tokens loaded

User mentions project → mnemos_recall(level="L2", wing="ProcureTrack")
  → L2: read room summaries under that wing
  → +300-500 tokens

User asks specific question → mnemos_search(...)
  → L3: semantic search returns relevant drawers
  → +200-400 tokens per query
```

### Summary Generation

- **With API key:** Claude generates smart summary for `_wing.md`
- **Without key:** First sentence of last 5 drawers concatenated

---

## 8. Knowledge Graph

### Schema (SQLite)

```sql
CREATE TABLE entities (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL,  -- person, project, technology, concept
    properties TEXT,     -- JSON
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE triples (
    id INTEGER PRIMARY KEY,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object TEXT NOT NULL,
    valid_from TEXT,      -- temporal: when this became true
    valid_to TEXT,        -- temporal: when this stopped being true (NULL = current)
    confidence REAL DEFAULT 1.0,
    source_file TEXT,
    created_at TEXT
);
```

### Temporal Queries

```python
# Current state
graph.query_entity("ProcureTrack")
# → uses Supabase (since 2026-03), has approval-flow (since 2026-04)

# Historical state
graph.query_entity("ProcureTrack", as_of="2026-03-15")
# → uses LightRAG (was active then, now closed)

# Timeline
graph.timeline("ProcureTrack")
# → chronological list of all events and changes
```

---

## 9. MCP Tools (8 Tools)

### Core Tools (v0.1)

**`mnemos_search`** — Search memories
```python
mnemos_search(
    query: str,
    wing: str = None,
    room: str = None,
    hall: str = None,
    limit: int = 5,
    rerank: bool = True
) → [{text, wing, room, hall, score, source, date}]
```

**`mnemos_add`** — Add a new memory
```python
mnemos_add(
    text: str,
    wing: str,
    room: str,
    hall: str = "facts",
    importance: float = 0.5
) → {drawer_id, obsidian_path, message}
```

**`mnemos_mine`** — Mine files for memories
```python
mnemos_mine(
    path: str,
    mode: str = "auto",
    use_llm: bool = True
) → {files_scanned, drawers_created, entities_found, skipped}
```

**`mnemos_status`** — System status
```python
mnemos_status()
→ {total_drawers, wings, rooms, entities, last_mine, vault_path, chromadb_synced}
```

### Second Wave Tools (v0.2)

**`mnemos_recall`** — Load memory context
```python
mnemos_recall(
    level: str = "L1",
    wing: str = None
) → {level, token_count, content}
```

**`mnemos_graph`** — Query entity relationships
```python
mnemos_graph(
    entity: str,
    as_of: str = None,
    depth: int = 1
) → {entity, relations: [{predicate, object, since}]}
```

**`mnemos_timeline`** — Chronological entity history
```python
mnemos_timeline(
    entity: str,
    from_date: str = None,
    to_date: str = None
) → [{date, event}]
```

**`mnemos_wake_up`** — Session startup context
```python
mnemos_wake_up()
→ {identity, wings_summary, recent_activity, pending_sync, token_count}
```

---

## 10. Configuration

### `mnemos.yaml` (vault root)

```yaml
version: 1

vault:
  path: "<auto-detected>"

palace:
  root: "Mnemos"
  recycled: "Mnemos/_recycled"
  identity: "Mnemos/Identity"

mining:
  languages: [tr, en]
  use_llm: true
  llm_model: "claude-sonnet-4-6"
  sources:
    - path: "Sessions/"
      mode: sessions
    - path: "Topics/"
      mode: general
    - path: "Mnemos/Wings/"
      mode: skip

search:
  default_limit: 5
  rerank: true
  rerank_model: "claude-haiku-4-5"

watcher:
  enabled: true
  ignore:
    - ".obsidian/"
    - "Mnemos/_recycled/"
    - "*.canvas"
    - "Templates/"

halls:
  - decisions
  - facts
  - events
  - preferences
  - problems

storage:
  chromadb_path: "Mnemos/.chromadb"
  graph_path: "Mnemos/.graph.db"
  mine_log: "Mnemos/.mine_log.json"
```

---

## 11. Project Structure (GitHub Repo)

```
mnemos/
├── pyproject.toml
├── LICENSE                 # MIT
├── README.md
├── mnemos/
│   ├── __init__.py
│   ├── __main__.py         # python -m mnemos.server
│   ├── cli.py              # mnemos init / mine / search / status
│   ├── server.py           # MCP server (8 tools)
│   ├── palace.py           # wing/room/hall management
│   ├���─ miner.py            # hybrid mining engine
│   ├── search.py           # 3-layer search
│   ├── graph.py            # SQLite knowledge graph
│   ├── obsidian.py         # vault I/O + watcher
│   ├── stack.py            # L0-L3 memory stack
│   ├── config.py           # mnemos.yaml reader
│   └── patterns/
│       ├── tr.yaml
│       ├── en.yaml
│       └── base.yaml
├── tests/
��   ├── test_palace.py
│   ├── test_miner.py
│   ├── test_search.py
│   ├── test_graph.py
│   ├── test_obsidian.py
│   ├── test_stack.py
│   ├── test_watcher.py
│   ├── test_config.py
│   ├── test_integration.py
│   └── fixtures/
│       ├── sample_session.md
│       ├── sample_topic.md
│       └── sample_vault/
├── examples/
│   ├── sample_vault/
│   └── mnemos.yaml
└── docs/
    ├── architecture.md
    ├── configuration.md
    └── contributing.md
```

---

## 12. Dependencies

```toml
[project]
name = "mnemos"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "chromadb>=1.0",
    "mcp>=1.0",
    "watchdog>=4.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
llm = ["anthropic>=0.40"]

[project.scripts]
mnemos = "mnemos.cli:main"
```

- `pip install mnemos` → regex-only mode
- `pip install mnemos[llm]` → Claude API mining + reranking

---

## 13. Release Plan

### v0.1.0 — "First Breath"
- Core 4 tools (search, add, mine, status)
- Regex-only mining (LLM optional)
- ChromaDB + Obsidian dual storage
- Watcher (file monitoring + sync)
- CLI (init, mine, search, status)
- tr + en language support
- Published on PyPI

### v0.2.0 — "Full Memory"
- Second wave tools (recall, graph, timeline, wake_up)
- L0-L3 memory stack
- Knowledge graph (temporal triples)
- Claude API mining + reranking
- mnemos_forget + _recycled mechanism

### v0.3.0 — "Community"
- Additional language support (de, es, fr, ja...)
- Obsidian plugin (TypeScript — in-vault UI)
- Benchmark suite (LongMemEval compatible)
- Contributing guide
- Demo video + blog post

---

## 14. Success Criteria

1. **Functional:** `mnemos init` → `mnemos mine` → `mnemos search` works end-to-end
2. **Quality:** Search returns relevant results for the user's real vault (16 existing files)
3. **Sync:** Obsidian file changes reflected in ChromaDB within 5 seconds
4. **Portable:** `pip install mnemos` works on Windows, macOS, Linux
5. **Open Source:** Published on GitHub + PyPI with MIT license
