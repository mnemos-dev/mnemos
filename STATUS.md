# Mnemos — Project Status

**Last updated:** 2026-04-15 (v0.3 task 3.3 delivered)
**Stable PyPI version:** `v0.2.0` · **In-progress:** `v0.3.0` (First-Run Experience)
**Canonical plan:** [`docs/ROADMAP.md`](docs/ROADMAP.md)

This file is the single-glance answer to: *why does Mnemos exist, what can it
do right now, and what will it do when the roadmap is complete?*

---

## 1. Why Mnemos exists

You have hundreds of Claude Code sessions stored as `~/.claude/projects/*.jsonl`.
Decisions, debugging notes, preferences, hard-won context — all locked in files
nobody re-opens. Every new session starts from zero. Your AI never *remembers
you*.

Prior art ([MemPalace](https://github.com/MemPalace/mempalace), 42K ★) proved
the palace architecture works, but:

- Stores memory in an opaque ChromaDB binary — users can't read/edit their own memory
- Mining is English-only regex — no Turkish, no multilingual
- Built as an isolated tool — doesn't plug into existing knowledge workflows

**The Mnemos bet:** make the palace **Obsidian-native**. Memory becomes plain
markdown in the user's existing vault. They can read, edit, delete, search with
Obsidian Graph View and Dataview — and their AI queries the same files via MCP.
Obsidian is the source of truth; the vector index is just an index.

**The v0.3 pivot:** after delivering the technical foundation (v0.1 core + v0.2
Phase 0 foundation), it became clear that without a one-command onboarding
flow that turns Claude Code history into palace memory, the tool is invisible
to external users. v0.3 is the "First-Run Experience" focused purely on that
gap.

---

## 2. What Mnemos can do today

### Stable — `pip install mnemos-dev` (v0.2.0)

**Memory palace core**
- ✅ Obsidian-native markdown storage — every memory is a `.md` file you can read
- ✅ Dual-backend vector index: ChromaDB (default) or sqlite-vec (lighter, cosine scoring)
- ✅ Palace hierarchy: Wing → Room → Hall → Drawer
- ✅ L0–L3 memory stack (identity / wing summaries / room details / deep search)
- ✅ Knowledge graph (SQLite, temporal triples)
- ✅ File watcher — Obsidian edits sync to vector index within seconds
- ✅ Soft-delete via `_recycled/` folder

**MCP integration (8 tools)**
- ✅ `mnemos_wake_up`, `mnemos_search`, `mnemos_recall`, `mnemos_add`,
  `mnemos_mine`, `mnemos_graph`, `mnemos_timeline`, `mnemos_status`
- ✅ Works with Claude Code, Cursor, ChatGPT, any MCP-compatible client

**Mining pipeline (Phase 0 Foundation)**
- ✅ 5 conversation formats auto-detected: Claude Code JSONL, Claude.ai JSON,
  ChatGPT JSON, Slack JSON, plain markdown/text
- ✅ Exchange-pair chunking (question + answer together)
- ✅ Room detection — 72+ folder/keyword patterns across 13 categories
- ✅ Heuristic entity detection (person vs project)
- ✅ 172 markers (87 EN + 85 TR) across 4 halls (decisions, preferences, problems, events)
- ✅ Prose extraction — filters code blocks, shell commands, tool noise
- ✅ Scoring + disambiguation (problem→milestone detection)
- ✅ Dual collection (raw + mined), Reciprocal Rank Fusion merge
- ✅ Case-insensitive wing resolution, `wing_override` for manual classification
- ✅ Bulk indexing API (10–25x faster mining than per-file)

**Quality / validation**
- ✅ 51 tests passing
- ✅ LongMemEval benchmark harness (`mnemos benchmark longmemeval`)
- 🟡 First measured recall: **~70% Recall@5** on a 10-question subset (Phase 1 will push this to ≥95%)

### In-progress — `v0.3.0` (unreleased)

- ✅ `refine-transcripts` Claude Code skill — JSONL → refined Sessions/.md
  with ledger-based resume, zero LLM cost, ships inside the repo via junction/symlink
- ✅ README repositioned around the Claude Code history use case
- ✅ `.mnemos-pending.json` schema + `mnemos.pending` module — atomic
  read/write/upsert API for resumable onboarding, status enum validation,
  schema versioning
- 🔲 `mnemos init` wizard expansion (discover → classify → pilot → confirm)
- 🔲 `mnemos import <source>` subcommand family (claude-code, chatgpt, slack, markdown, memory)
- 🔲 CONTRIBUTING.md
- 🔲 New-user simulation pilot
- 🔲 PyPI release

### Practical stats (author's vault)

- 277 drawers across 9 wings, 2-language (TR+EN) regex mining
- Cosine search scores healthy at 0.30–0.70 range
- 222 Claude Code JSONL transcripts awaiting refinement (pilot: 2 OK / 3 SKIP out of 5 sampled)

---

## 3. Where the roadmap ends up

When the full ROADMAP is delivered (v0.6), Mnemos will be:

### A turnkey on-ramp (v0.3)
- `mnemos init` discovers every knowledge source on your machine — Claude Code
  projects, Obsidian Topics/, past Sessions/, memory/ folders — and classifies
  them as curated vs raw
- Curated markdown is mined directly; raw transcripts are refined first via a
  Claude Code skill that runs inside your existing session (no extra API cost)
- `mnemos import <source>` lets you add sources later; `.mnemos-pending.json`
  tracks in-progress batches so a crashed session doesn't start over

### High-recall memory (v0.4, Phase 1)
- Claude API mining catches what regex misses — including the emotional hall
  that Phase 0 deferred to avoid false positives
- LLM reranking boosts search precision (top-50 → top-10)
- Contradiction detection: when a new memory says "we switched to Y" and an
  old memory says "we use X", the old one is auto-flagged stale
- Benchmark target: **≥95% Recall@5, ≥97% Recall@10**

### Self-maintaining (v0.5, Phase 2)
- Session hooks auto-mine at the end of each Claude Code session — zero manual
  `mnemos mine` commands
- Memory lifecycle: stale, never-queried memories decay; contradicted ones
  move to `_recycled/`
- Knowledge graph deepening — indirect queries like "what did Y-wing decide
  in the last N days about project X?"

### Community-ready (v0.6)
- Multi-language marker sets (de, es, fr, ja) with the same 80+ markers per language
- Obsidian plugin — in-vault UI: memory browser, timeline view, graph view
- Demo video + launch blog post
- Contributor onboarding (issue templates, good-first-issue tags)

### The end state

> *A new Claude Code user runs `pip install mnemos-dev && mnemos init`. Within
> ten minutes, every past session they've ever had is indexed into their
> Obsidian vault as plain markdown, classified by project and topic. From that
> day forward, every Claude Code session opens with relevant context already
> loaded, and every decision they make is persisted automatically. Their AI
> knows them. Their memory is human-readable. Nothing is locked in a proprietary
> binary.*

---

## Check-in rhythm

This file is updated whenever a ROADMAP checkbox flips. If you're reading it
months from now, expect section 2 to have grown and section 3 to have shrunk.
