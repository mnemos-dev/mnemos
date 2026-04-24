<h1 align="center">Mnemos</h1>
<p align="center"><strong>Turn your Claude Code history into a searchable memory palace.</strong></p>
<p align="center">Every conversation becomes markdown in your Obsidian vault. Every decision stays findable. Your AI finally remembers you.</p>
<p align="center">
  <a href="https://github.com/mnemos-dev/mnemos/actions/workflows/test.yml">
    <img src="https://github.com/mnemos-dev/mnemos/actions/workflows/test.yml/badge.svg?branch=main" alt="tests">
  </a>
  <a href="https://pypi.org/project/mnemos-dev/">
    <img src="https://img.shields.io/pypi/v/mnemos-dev.svg" alt="PyPI">
  </a>
  <a href="https://www.python.org/downloads/">
    <img src="https://img.shields.io/badge/python-3.10+-green.svg" alt="Python 3.10+">
  </a>
  <a href="https://github.com/mnemos-dev/mnemos/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License">
  </a>
  <a href="https://github.com/mnemos-dev/mnemos/blob/main/CODE_OF_CONDUCT.md">
    <img src="https://img.shields.io/badge/code%20of%20conduct-Contributor%20Covenant%202.1-ff69b4.svg" alt="Contributor Covenant">
  </a>
  <a href="https://github.com/MemPalace/mempalace">
    <img src="https://img.shields.io/badge/inspired%20by-MemPalace-purple.svg" alt="Inspired by MemPalace">
  </a>
</p>

<p align="center">
  📖 <strong><a href="STATUS.md">Project Status</a></strong> — what works today vs. what's coming ·
  🗺️ <strong><a href="docs/ROADMAP.md">Roadmap</a></strong> — the single canonical plan ·
  🤝 <strong><a href="CONTRIBUTING.md">Contributing</a></strong> — dev setup + conventions
</p>

---

## New here? Read this first

If you're new to Claude Code skills, MCP tools, or Obsidian, here is the whole
picture in plain language. **If you know what you're doing, skip to
[Quick Start](#quick-start).**

### The pieces, in plain language

**Claude Code** is the terminal CLI where you chat with Claude. Each time you
close a session and open a new one, Claude forgets everything about the last
one — there is no built-in long-term memory. Your past conversations are
sitting on disk as JSON Lines files under `~/.claude/projects/*.jsonl`, but
nothing reads them for you.

**Obsidian** is a free app that renders a folder of plain `.md` files as a
connected note-taking system. *You don't have to install it.* Mnemos writes
every memory as a plain markdown file regardless — Obsidian is just a nicer
UI if you want one. Any text editor works.

**MCP (Model Context Protocol)** is the plug-in system Claude Code uses to
talk to tools. When you install Mnemos, you register it as an MCP server —
from then on, Claude Code has a `mnemos_search` tool it can call on its own
whenever something in the conversation rings a bell from a past session.

### What Mnemos does, end to end

```
past Claude Code sessions (~/.claude/projects/*.jsonl)
            │
            │  refined into readable session notes
            ▼
  <vault>/Sessions/YYYY-MM-DD-slug.md          ← one .md per closed session
            │
            │  mined for decisions, preferences, problems, events
            ▼
  <vault>/Mnemos/wings/<topic>/<room>/*.md     ← classified memories
            │
            │  indexed for semantic search
            ▼
  vector index (ChromaDB or sqlite-vec — pick at init)
            │
            │  exposed over MCP
            ▼
  Claude Code → mnemos_search → relevant memories loaded into context
```

Everything lives as plain markdown in a folder *you* pick. Delete a `.md` file
and the memory is gone. No proprietary database you can't open.

### The happy path (≈ 5 minutes)

```bash
# 1. Install the package
pip install mnemos-dev

# 2. Scaffold your vault — the wizard walks through discovery and choice.
#    Answers are in TR and EN.
mnemos init

# 3. Register Mnemos as an MCP server so Claude Code can call its tools.
claude mcp add mnemos -- python -m mnemos --vault /path/to/your/vault

# 4. Wire up the auto-refine hook so every new Claude Code session
#    catches up on the latest closed transcripts in the background.
mnemos install-hook
mnemos install-statusline
```

That's it. The next time you open Claude Code, the status bar will show a
`mnemos:` line reporting what it just refined. Ask about something from a past
session and watch Claude call `mnemos_search` on its own.

### Common questions before you start

**"Will this burn through my Anthropic API credits?"** — No. Refinement runs
as a Claude Code *skill*, using your existing Claude Code subscription.
Mnemos itself never calls the Anthropic API. `pip install mnemos-dev` brings
the tooling; the AI work happens inside the CLI you already pay for.

**"What if I don't want to use Obsidian?"** — Works identically. The vault
is just a folder of `.md` files; any editor reads them. You can add
Obsidian later if the graph view and inline links appeal to you.

**"Which backend should I pick — ChromaDB or sqlite-vec?"** — ChromaDB is the
default and works well on macOS/Linux. If you are on Windows with Python
3.14, or want a single-file index you can copy around, choose sqlite-vec —
the 2026-04-17 parity benchmark showed identical recall (R@5=0.90) on both.
You can switch any time with `mnemos migrate --backend <name>`.

**"Is my vault going to explode in size?"** — The author's vault has 683
memories in ~9 MB of markdown plus a 40 MB ChromaDB index after 122
refined sessions. Disk impact is small; everything compresses well because
it's plain text.

**"Can I run this on an existing vault I already use for other notes?"** —
Yes, but keep the `Mnemos/` subfolder to Mnemos-managed content; it uses
that as the palace root. Your existing `Topics/`, `memory/`, and any other
folders are left alone unless you explicitly point `mnemos import` at them.

---

## The Problem

You've had hundreds of Claude Code sessions. Decisions, debugging notes, hard-won context — all locked in `~/.claude/projects/*.jsonl` files nobody ever opens again. Every new session starts from zero.

## What Mnemos Does

Mnemos turns that history into a **memory palace** any future Claude Code session can search:

1. **Refine** — a bundled Claude Code skill reads your JSONL transcripts and writes focused session notes (decisions, outcomes, open questions) into your Obsidian vault. High signal, no tool noise.
2. **Mine** — regex + optional LLM extraction pulls individual memories out of those notes and classifies them by project, topic, and type.
3. **Recall** — 8 MCP tools let any Claude Code / Cursor / ChatGPT session search, graph, and load relevant context.

Storage is plain markdown in your vault. You read it, edit it, organize it. Two swappable vector backends index it for semantic search — **ChromaDB** (default, mature) or **sqlite-vec** (single-file, robust on Windows/Python 3.14). A 2026-04-17 parity benchmark showed they produce identical recall; switch any time with `mnemos migrate --backend <name>`. **Obsidian is the source of truth** — delete a note in Obsidian and the memory is gone.

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
most recent closed transcripts in the background (via a SessionStart hook
installed by `mnemos init`). The statusline shows a one-shot snapshot at
session start; check `<vault>/.mnemos-hook.log` for detailed progress.
Open sessions are protected — PID-based markers ensure no transcript is
refined while its window is still active.

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

Every memory is a `.md` file with YAML frontmatter. Two backends ship behind the same interface: **ChromaDB** (default) or **sqlite-vec**. Pick one during `mnemos init`, or swap later with `mnemos migrate --backend sqlite-vec`. If it's not in your vault, it doesn't exist.

## Cross-context recall

When the cwd-based auto-briefing doesn't cover what you need (e.g., you're
working in one project but want a decision from another), use the
`/mnemos-recall` slash command in any Claude Code session:

```
/mnemos-recall "what output format did the PO skill use"
```

The skill runs in the current session (no subprocess): searches the palace
via the MCP, reads the top matching drawers, and synthesizes a short
narrative answer with `[[wikilink]]` citations back to the drawer files.
If the embedding-based search is weak for your query (common for unique
project names or terms not yet mined into a dedicated drawer), the skill
falls back to a keyword grep over the vault's `Sessions/` folder and
synthesizes from the top matching Session summaries instead — so even
"tavuklu bir oyun yapacaktık biz sanki?" style queries that embeddings
miss still surface the right conversation.

Use the auto-briefing for "where am I in this project" (silent, per-cwd).
Use `/mnemos-recall` for "remind me about X from somewhere else"
(explicit, query-based).

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

## Troubleshooting

### Which backend am I on?

```bash
mnemos status
```

The first line tells you — e.g.

    Backend: sqlite-vec (search.sqlite3 · 8027 drawers · 42.3 MB)

### ChromaDB index corruption or errors

If `mnemos search` / `mnemos mine` fails with an HNSW / DatabaseError / segfault-style message from ChromaDB, the single recovery command is:

```bash
mnemos migrate --backend sqlite-vec
```

This backs up the broken `.chroma/` directory (date-stamped, never overwritten), updates `mnemos.yaml`, and rebuilds the index from your vault's `Sessions/` + `Topics/` + `memory/` folders. **No memories are lost** — your `.md` files are the source of truth. Run `--dry-run` first if you want to see the plan without changing anything:

```bash
mnemos migrate --backend sqlite-vec --dry-run
```

`mnemos init` and every runtime error path also suggest this command, so a user seeing an unfamiliar traceback has an actionable recovery line.

### Switching back to ChromaDB

Same command, other way around:

```bash
mnemos migrate --backend chromadb
```

Backups are kept under `<palace>/.chroma.bak-YYYY-MM-DD/` and `<palace>/search.sqlite3.bak-YYYY-MM-DD` — delete them manually when you're confident the new backend is good.

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
   (or        (knowledge graph)
   sqlite-vec)
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
- **v0.3** — **First-run experience** ✅ released:
  refine-transcripts skill,
  `.mnemos-pending.json` resume mechanism,
  `mnemos init` 5-phase discover/classify/import wizard,
  `mnemos import {claude-code,chatgpt,slack,markdown,memory}` subcommand family,
  CLI i18n (TR + EN), CONTRIBUTING.md,
  SessionStart auto-refine hook (`mnemos install-hook`),
  `mnemos install-statusline`,
  no-flicker / no-mid-conversation-refire fixes,
  legacy session-memory deprecation guide,
  new-user simulation pilot.
- **v0.3.1** — **Backend UX** ✅ released:
  `mnemos init` backend picker (ChromaDB / sqlite-vec),
  `mnemos migrate --backend <name>` with dry-run + dated backups,
  `BackendInitError` with migrate recipe,
  `mnemos status` backend summary line,
  README Troubleshooting recipes.
- **v0.3.2** — **Palace Hygiene** ✅ released:
  TR-aware wing canonicalization,
  lazy hall / `_wing.md` / `_room.md` creation,
  source-date filenames + H1+wikilink drawer bodies,
  entity hygiene (no tags, case-preserve dedup),
  atomic `mnemos mine --rebuild` (backup → drop+reinit → re-mine → verify → rollback),
  distribution-ready memory-source handling (additive `_resolve_sources`, yaml persistence on import).
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
