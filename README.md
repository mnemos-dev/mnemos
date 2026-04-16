<h1 align="center">Mnemos</h1>
<p align="center"><strong>Turn your Claude Code history into a searchable memory palace.</strong></p>
<p align="center">Every conversation becomes markdown in your Obsidian vault. Every decision stays findable. Your AI finally remembers you.</p>
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
  <a href="https://github.com/mnemos-dev/mnemos/releases">
    <img src="https://img.shields.io/badge/version-0.2.0-orange.svg" alt="v0.2.0">
  </a>
</p>

<p align="center">
  📖 <strong><a href="STATUS.md">Project Status</a></strong> — what works today vs. what's coming ·
  🗺️ <strong><a href="docs/ROADMAP.md">Roadmap</a></strong> — the single canonical plan ·
  🤝 <strong><a href="CONTRIBUTING.md">Contributing</a></strong> — dev setup + conventions
</p>

---

## The Problem

You've had hundreds of Claude Code sessions. Decisions, debugging notes, hard-won context — all locked in `~/.claude/projects/*.jsonl` files nobody ever opens again. Every new session starts from zero.

## What Mnemos Does

Mnemos turns that history into a **memory palace** any future Claude Code session can search:

1. **Refine** — a bundled Claude Code skill reads your JSONL transcripts and writes focused session notes (decisions, outcomes, open questions) into your Obsidian vault. High signal, no tool noise.
2. **Mine** — regex + optional LLM extraction pulls individual memories out of those notes and classifies them by project, topic, and type.
3. **Recall** — 8 MCP tools let any Claude Code / Cursor / ChatGPT session search, graph, and load relevant context.

Storage is plain markdown in your vault. You read it, edit it, organize it. ChromaDB indexes it for semantic search, but **Obsidian is the source of truth** — delete a note in Obsidian and the memory is gone.

## Quick Start

```bash
# 1. Install
pip install mnemos-dev

# 2. Scaffold your vault — interactive wizard:
#    discovers Claude Code transcripts + vault Sessions/memory/Topics,
#    asks [A]ll / [S]elective / [L]ater, then mines what you choose.
#    Resumable via .mnemos-pending.json. TR + EN.
mnemos init

# 3. Install the refinement skill (one-time)
#    Windows:
mklink /J "%USERPROFILE%\.claude\skills\mnemos-refine-transcripts" \
  "<mnemos-repo>\skills\mnemos-refine-transcripts"
#    macOS / Linux:
ln -s <mnemos-repo>/skills/mnemos-refine-transcripts \
  ~/.claude/skills/mnemos-refine-transcripts

# 4. Wire it to Claude Code
claude mcp add mnemos -- python -m mnemos --vault /path/to/your/vault

# 5. In a Claude Code session:
/mnemos-refine-transcripts --limit 5   # pilot: 5 JSONLs → Sessions/
mnemos mine Sessions/                   # extract memories into the palace
```

Or skip the manual flow above and let `mnemos init` walk you through everything. Add sources later with `mnemos import claude-code`, `mnemos import chatgpt <export.json>`, etc.

After init, every new Claude Code session automatically refines + mines the
most recent transcripts in the background (via a SessionStart hook installed
by `mnemos init`). Check your statusline for live progress, or tail
`<vault>/.mnemos-hook.log`.

Future Claude Code sessions automatically pull context via `mnemos_wake_up` + `mnemos_search`.

## The Refinement Skill

`skills/mnemos-refine-transcripts/` ships with the repo. After the symlink/junction above, Claude Code sees it as `/mnemos-refine-transcripts`. The skill:

- Discovers JSONL transcripts under `~/.claude/projects/`
- Runs a prose extractor (drops tool calls, hooks, sidechains)
- Applies the canonical refinement prompt at `docs/prompts/refine-transcripts.md` — one source of rules, no drift
- Writes value-carrying sessions to `<vault>/Sessions/<YYYY-MM-DD>-<slug>.md`, skips noise
- Keeps a local ledger (`skills/mnemos-refine-transcripts/state/processed.tsv`) so nothing gets reprocessed
- Pilots 5 at a time before committing to the full batch

The skill does **not** call any LLM API — it runs inside your existing Claude Code session. Zero additional cost, zero extra dependencies.

### Migrating from older session-memory setups

If you were an early adopter and your `~/.claude/` still has any of these, they are now superseded by the auto-refine hook installed by `mnemos init` and can be removed safely:

- `~/.claude/skills/session-memory/` — pre-mnemos manual SAVE-on-keyword skill. The auto-refine hook captures every transcript automatically; no need to type "bye" / "kaydet" anymore. Delete the folder.
- `~/.claude/hooks/mnemos-session-mine.py` (and its `mnemos-mine-worker.py` / `mnemos-mined-transcripts.json` / `mnemos-mine.lock` siblings) — the original raw-transcript miner. Replaced by the refine-then-mine pipeline (refining drops 99% of tool noise before mining). Delete those files and remove the matching `SessionStart` entry from `~/.claude/settings.json` (keep only the entry whose `_managed_by` is `mnemos-auto-refine`).

Mnemos itself doesn't auto-delete user files — these are one-time manual cleanups.

## Why Not Just Raw Transcripts?

| | Raw JSONL | Refined Sessions/ |
|--|-----------|-------------------|
| **Size** | 50-500 KB each, 99% tool noise | 10-50 lines of actual decisions |
| **Searchability** | Semantic search drowns in tool calls | Every hit is a real turn |
| **Readability** | JSON blobs | Human markdown |
| **Portability** | Claude Code format only | Markdown, any tool |

Refinement is selective: curated `.md` files (memory, Topics/, hand-written Sessions/) skip refinement and are mined directly. Noisy sources (JSONL, email, PDF) get refined first.

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

Every memory is a `.md` file with YAML frontmatter. ChromaDB (or optional sqlite-vec) runs alongside as a vector index. If it's not in your vault, it doesn't exist.

## MCP Tools

| Tool | Description |
|------|-------------|
| `mnemos_wake_up` | Session startup context (~200 tokens: identity + wings) |
| `mnemos_search` | Semantic search with wing/room/hall filters + dual collection (raw/mined/both) |
| `mnemos_recall` | Load context (L0 identity, L1 summaries, L2 details) |
| `mnemos_add` | Add a new memory |
| `mnemos_mine` | Extract memories from files or directories |
| `mnemos_graph` | Query entity relationships |
| `mnemos_timeline` | Chronological entity history |
| `mnemos_status` | Palace statistics |

Works with **Claude Code**, **Cursor**, **ChatGPT**, and any MCP-compatible client.

## Mining

Mnemos extracts memories using a 10-step pipeline:

1. **Format detection** — Claude Code JSONL, ChatGPT JSON, Slack JSON, or plain markdown
2. **Conversation normalization** — chat exports → standard transcript format
3. **Prose extraction** — filters code blocks, shell commands, non-human text
4. **Exchange-pair chunking** — keeps questions and answers together
5. **Room detection** — 72+ folder/keyword patterns across 13 categories
6. **Entity detection** — heuristic person/project classification
7. **172 regex markers** — 87 English + 85 Turkish across 4 halls (decisions, preferences, problems, events)
8. **Scoring + disambiguation** — confidence-based classification
9. **Claude API** (optional) — catches what regex misses, works in any language

```bash
mnemos mine Sessions/                                  # the usual flow
mnemos mine ~/chatgpt-export.json                      # auto-detected format
mnemos mine Sessions/ --rebuild                        # wipe & re-index
pip install mnemos-dev[llm] && mnemos mine Sessions/ --llm   # LLM-assisted
```

### Conversation Formats

| Format | Source | Auto-detected |
|--------|--------|:---:|
| Claude Code JSONL | `~/.claude/projects/*/conversations/` | ✅ |
| Claude.ai JSON | claude.ai export | ✅ |
| ChatGPT JSON | chatgpt.com export | ✅ |
| Slack JSON | Slack workspace export | ✅ |
| Plain text / Markdown | Any `.md` or `.txt` | ✅ |

### External Sources (Read-Only)

```bash
mnemos mine ~/some/notes --external
```

External sources are mined once. Source files are **never modified or watched**.

## File Watcher

Changes you make in Obsidian sync to the vector index automatically:

| Action | Result |
|--------|--------|
| Add a note | Indexed |
| Edit a note | Re-indexed |
| Delete a note | Removed from index |
| Move a note | Metadata updated |

Runs inside the MCP server. Detects offline changes on restart.

## Memory Stack (L0–L3)

Efficient context loading — your AI knows you without burning tokens:

| Level | Content | Tokens | Loaded |
|-------|---------|--------|--------|
| L0 | Identity | ~50 | Every session |
| L1 | Wing summaries | ~150 | Every session |
| L2 | Room details | ~300–500 | When topic mentioned |
| L3 | Deep search | ~200–400 | When asked |

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
   (dual)     (knowledge graph)
    |    |
  raw  mined       ← Reciprocal Rank Fusion merge
    |    |
    v    v
  +-----------------------+
  |   Obsidian Vault      |
  |   (.md files = truth) |
  +-----------------------+
```

## Benchmarks

Mnemos uses [LongMemEval](https://huggingface.co/datasets/xiaowu0162/LongMemEval) (500 questions across 54 conversation sessions) for recall measurement.

```bash
pip install mnemos-dev[benchmark]
mnemos benchmark longmemeval              # all 500 questions
mnemos benchmark longmemeval --limit 10   # quick smoke
mnemos benchmark longmemeval --mode raw-only
```

| Mode | Description |
|------|-------------|
| `raw-only` | Verbatim collection only |
| `mined-only` | Classified collection only |
| `combined` | Both, with RRF merge (default) |

## Roadmap

- **v0.1** — Core palace architecture, 8 MCP tools, basic regex mining
- **v0.2** — Dual collection, 5 conversation formats, 172 markers, LongMemEval benchmark harness
- **v0.3** — **First-run experience** (in progress):
  refine-transcripts skill ✅,
  `.mnemos-pending.json` resume mechanism ✅,
  `mnemos init` 5-phase discover/classify/import wizard ✅,
  `mnemos import {claude-code,chatgpt,slack,markdown,memory}` subcommand family ✅,
  CLI i18n (TR + EN) ✅,
  CONTRIBUTING.md ✅,
  SessionStart auto-refine hook (`mnemos install-hook`) ✅,
  `mnemos install-statusline` ✅,
  no-flicker / no-mid-conversation-refire fixes ✅,
  legacy session-memory deprecation guide ✅.
  Remaining: new-user pilot, PyPI release.
- **v0.4** — AI engine: Claude API mining quality pass, reranking, contradiction detection
- **v0.5** — Automation: session hooks, memory lifecycle, knowledge graph deepening
- **v0.6** — Ecosystem: specialist agents, multi-source connectors, Obsidian plugin

## vs. MemPalace

[MemPalace](https://github.com/MemPalace/mempalace) proved structured memory architecture works for AI. Mnemos takes the same idea and makes it Obsidian-native and Claude Code-first.

| | MemPalace | Mnemos |
|--|-----------|--------|
| **Storage** | ChromaDB binary (opaque) | Obsidian markdown (you can read it) |
| **Mining** | English regex only | Hybrid: regex + Claude API (any language) |
| **Primary source** | Generic strings | Claude Code JSONL via refinement skill |
| **Access** | AI only | You AND your AI |
| **Deletion** | API call | Delete in Obsidian, auto-synced |
| **Ecosystem** | Standalone | Obsidian Graph View, Dataview, plugins |

## Contributing

```bash
git clone https://github.com/mnemos-dev/mnemos.git
cd mnemos
pip install -e ".[dev,llm]"
pytest tests/ -v
```

Built from scratch (not a fork) — inspired by [MemPalace](https://github.com/MemPalace/mempalace)'s palace architecture.

## License

MIT — Copyright 2026 Tugra Demirors / GYP Energy
