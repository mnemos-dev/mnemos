<h1 align="center">Mnemos</h1>
<p align="center"><strong>Narrative-first AI memory for Claude Code, built on plain markdown you own.</strong></p>
<p align="center">Your past sessions become a connected graph your AI can read, traverse, and brief you with — automatically, every time you start working.</p>
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
            │  refined into rich, structured Session notes
            ▼
  <vault>/Sessions/YYYY-MM-DD-slug.md          ← one .md per closed session
            │  (Decisions / Problems / Next steps + [[wikilinks]])
            │
            │  wikilinks form a sparse, readable graph
            ▼
  <vault>/_identity/L0-identity.md             ← who you are, synthesized
            │
            │  briefing skill walks the graph at session start
            ▼
  Claude Code → cwd-aware briefing → 3-layer narrative in your context
```

Everything lives as plain markdown in a folder *you* pick. Delete a `.md` file
and the memory is gone. No proprietary database you can't open.

### The happy path (≈ 5 minutes)

```bash
# 1. Install the package
pip install mnemos-dev

# 2. Scaffold your vault — the wizard walks through discovery and choice.
mnemos init

# 3. Bootstrap your Identity Layer (~5–10 min, one-shot)
mnemos identity bootstrap

# 4. Register Mnemos as an MCP server so Claude Code can call its tools.
claude mcp add mnemos -- python -m mnemos --vault /path/to/your/vault

# 5. Wire up the SessionStart briefing hook (atomic, idempotent).
mnemos install-hook --v1
mnemos install-statusline
```

That's it. The next time you open Claude Code in a project directory, the
briefing skill silently assembles "where am I in this project" context from
your matching Sessions and injects it into your first turn. Ask about
something from a past conversation and Claude can call `mnemos_search` on
its own.

### Common questions before you start

**"Will this burn through my Anthropic API credits?"** — No. Refinement,
briefing, and recall all run as Claude Code *skills*, using your existing
Claude Code subscription. Mnemos itself never calls the Anthropic API.
`pip install mnemos-dev` brings the tooling; the AI work happens inside the
CLI you already pay for.

**"What if I don't want to use Obsidian?"** — Works identically. The vault
is just a folder of `.md` files; any editor reads them. You can add
Obsidian later if the graph view and inline links appeal to you.

**"Which backend should I pick — ChromaDB or sqlite-vec?"** — ChromaDB is the
default and works well on macOS/Linux. If you are on Windows with Python
3.14, or want a single-file index you can copy around, choose sqlite-vec —
the 2026-04-17 parity benchmark showed identical recall (R@5=0.90) on both.
You can switch any time with `mnemos reindex --backend <name>`.

**"Is my vault going to explode in size?"** — A typical author vault sits
around ~9 MB of markdown plus a small vector index after ~100 refined
sessions. Disk impact is small; everything compresses well because it's
plain text.

**"Can I run this on an existing vault I already use for other notes?"** —
Yes. Mnemos owns `<vault>/Sessions/` and `<vault>/_identity/`. Your
existing `Topics/`, `memory/`, and any other folders are left alone.

---

## Why Mnemos exists

Mnemos started inspired by [MemPalace](https://github.com/MemPalace/mempalace),
the project that proved structured memory works for AI. The first four
months built on its foundation — Obsidian-native storage, multilingual
mining, an LLM-quality pipeline that turned Claude Code conversation history
into ~600 atomic memory fragments classified by category (decisions,
problems, preferences, events).

Then we measured it.

**Three things didn't survive contact with real data:**

1. **Vector recall on small fragments converges.** The Reciprocal Rank
   Fusion score distribution clusters in a narrow 0.014–0.017 band on
   ~600 fragments. The supposed precision boost from atomization doesn't
   materialize on conversational data — the embeddings of two unrelated
   decisions are barely distinguishable from the embeddings of two related
   ones once you've cut them small enough.
2. **LLM synthesis prefers narrative.** When asked to brief a project, the
   model produces tighter, more accurate answers from full session notes
   (one conversation = one rich markdown file) than from fragmented
   decision atoms it has to glue back together. The chronology and
   cause-and-effect chains live in the prose, not in the atoms.
3. **A 600-node graph is fancy, not navigable.** The user doesn't traverse
   it manually; the AI doesn't traverse it programmatically. The graph
   became a poster — beautiful, unreadable.

**Mnemos v1.0 is a different paradigm: narrative-first.**

- **Sessions stay whole.** Each Claude Code conversation becomes one rich
  markdown note in your vault, with structured sections (decisions,
  problems, next steps, summary). The session is the unit of memory.
- **Wikilinks connect Sessions through shared entities.** When two
  sessions both mention `[[Project X]]` or `[[Customer Y]]`, the link
  bridges them — producing a sparse, readable graph instead of a dense,
  atomic one.
- **Skills traverse the graph.** Briefing and recall don't just
  keyword-search; they follow wikilinks, read backlinks, and resolve entity
  neighborhoods to assemble context the way a human would scroll through
  related notes.

This isn't MemPalace done better — it's the path we found by walking
MemPalace's path and meeting its wall. Credit for the wall belongs to the
original project; without it, there's no map.

The atomic-fragmentation paradigm is broader than any single project (mem0,
several LangChain memory backends, "vector database as memory" approaches
all share the same hypothesis: smaller is sharper). Mnemos v1.0 is a
counter-bet — bigger units, denser links, smarter traversal.

---

## What "narrative-first" means in practice

**You write nothing.** Mnemos refines your Claude Code transcripts in the
background and produces one Session note per closed conversation, in your
existing Obsidian vault, in plain markdown.

**Each Session is a rich note**, not a transcript. It has:

- A title and date
- A `cwd:` frontmatter field (which project this session was about)
- Structured `tags:` (`proj/x`, `tool/y`, `person/z`, `file/r`, `skill/s`)
- An "Özet" / "Summary" section
- "Alınan Kararlar" / "Decisions" — what was decided
- "Sorunlar" / "Problems" — what went wrong, what's still open
- "Sonraki Adımlar" / "Next steps"
- Inline `[[wikilinks]]` to entities (projects, people, tools, files)

**Sessions form a graph.** Two sessions linking to `[[Project X]]` are
neighbors. Obsidian shows this in Local Graph View. Mnemos's skills walk it
programmatically.

**Two skills consume the graph:**

- **`mnemos-briefing`** runs automatically when you start Claude Code in a
  directory. It reads your Identity Layer (3K), pulls Sessions with
  matching `cwd:` (8K), expands one wikilink hop for cross-context entity
  neighborhoods (4K), and synthesizes a 200–400 word briefing covering
  active decisions, revised decisions, open problems, and what's likely
  next. Hard cap: 15K tokens. Injected before your first turn.
- **`/mnemos-recall <query>`** is for cross-context questions: working in
  directory A but asking about work done in directory B. It does vector
  search over Sessions, follows wikilinks to gather neighborhood context,
  and synthesizes a 150–300 word narrative answer with clickable wikilink
  citations.

Both skills run inside your existing Claude Code session via the
subscription quota. **Zero per-query API cost.**

---

## Quick Start

```bash
# 1. Install
pip install mnemos-dev

# 2. Scaffold your vault — interactive wizard:
#    discovers Claude Code transcripts + vault Sessions/Topics,
#    asks [A]ll / [S]elective / [L]ater. TR + EN.
mnemos init

# 3. Install the refinement skill (one-time)
#    Windows:
mklink /J "%USERPROFILE%\.claude\skills\mnemos-refine-transcripts" \
  "<mnemos-repo>\skills\mnemos-refine-transcripts"
#    macOS / Linux:
ln -s <mnemos-repo>/skills/mnemos-refine-transcripts \
  ~/.claude/skills/mnemos-refine-transcripts

# 4. Wire to Claude Code
claude mcp add mnemos -- python -m mnemos --vault /path/to/your/vault

# 5. Bootstrap the Identity Layer (one-shot, ~5–10 min)
mnemos identity bootstrap

# 6. Install SessionStart briefing hook (v1, atomic, idempotent)
mnemos install-hook --v1
mnemos install-statusline
```

After this, every new Claude Code session automatically refines the most
recent closed transcripts in the background and assembles a cwd-aware
briefing for your first turn. The statusline shows a one-shot snapshot at
session start; check `<vault>/.mnemos-hook.log` for detailed progress. Open
sessions are protected — PID-based markers ensure no transcript is refined
while its window is still active.

### Identity Layer

After `mnemos init`, run `mnemos identity bootstrap` (~5–10 min, one-shot)
to generate `<vault>/_identity/L0-identity.md` — a structured user profile
synthesized from your Sessions. The briefing skill reads this as a base
layer on every session start, so your AI knows you, not just your last
chat.

Update later with `mnemos identity refresh` (incremental, ~1–2 min). Run
`mnemos identity show` to view the current profile or `mnemos identity
rollback` to restore a previous snapshot.

### The Refinement Skill

`skills/mnemos-refine-transcripts/` ships with the repo. After the
symlink/junction above, Claude Code sees it as `/mnemos-refine-transcripts`.
The skill:

- Discovers JSONL transcripts under `~/.claude/projects/`
- Runs a prose extractor (drops tool calls, hooks, sidechains)
- Applies the canonical refinement prompt at
  `docs/prompts/refine-transcripts.md` — one source of rules, no drift
- Writes value-carrying Sessions to `<vault>/Sessions/<YYYY-MM-DD>-<slug>.md`,
  skips noise, and emits the v2 tag + wikilink hybrid format
- Keeps a local ledger so nothing gets reprocessed
- Pilots 5 at a time before committing to a full batch

The skill does **not** call any LLM API — it runs inside your existing
Claude Code session. Zero additional cost, zero extra dependencies.

### Cross-context recall

When the cwd-based auto-briefing doesn't cover what you need (e.g., you're
working in one project but want a decision from another), use the
`/mnemos-recall` slash command in any Claude Code session:

```
/mnemos-recall "what output format did the PO skill use"
```

The skill runs in the current session (no subprocess): searches Sessions
via the MCP, walks wikilinks to gather neighborhood context, and
synthesizes a short narrative answer with `[[wikilink]]` citations back to
the Session files. If embedding-based search is weak for your query
(common for unique project names), it falls back to a keyword grep over
the vault's `Sessions/` folder so even "tavuklu bir oyun yapacaktık biz
sanki?" style queries surface the right conversation.

Use the auto-briefing for "where am I in this project" (silent, per-cwd).
Use `/mnemos-recall` for "remind me about X from somewhere else"
(explicit, query-based).

---

## Architecture

```
Claude Code / Cursor / ChatGPT
        |
        | MCP (stdio)
        v
  +----------------------+
  |  Mnemos Server       |
  |  (5 MCP tools)       |
  +----|-----------|-----+
       |           |
   Sessions    Identity
   (Obsidian   (L0
    .md)       profile)
       \         /
        \       /  vector index
         v     v   (ChromaDB or sqlite-vec)
  +-----------------------+
  |   Obsidian Vault      |
  |   (.md files = truth) |
  +-----------------------+
```

**Storage:** plain markdown in `<vault>/Sessions/` and
`<vault>/_identity/`. Two swappable vector backends index Sessions for
semantic search — **ChromaDB** (default, mature) or **sqlite-vec**
(single-file, robust on Windows/Python 3.14). Switch any time with
`mnemos reindex --backend <name>`.

**Source of truth:** Obsidian. Delete a `.md` file and the memory is gone —
the file watcher cleans the index. No hidden state.

**Graph:** Obsidian's wikilink graph. `mnemos_graph(entity)` and
`mnemos_timeline(entity)` query the wikilink graph in real time; tool
signatures unchanged from v0.x.

## MCP Tools

| Tool | Description |
|------|-------------|
| `mnemos_wake_up` | Session startup context (~200 tokens: Identity + recent Sessions) |
| `mnemos_search` | Semantic search over Sessions with cwd / tag filters |
| `mnemos_recall` | Load context (L0 Identity, cwd Sessions, wikilink expansion) |
| `mnemos_graph` | Query wikilink-graph entity relationships |
| `mnemos_timeline` | Chronological entity history via Sessions |

Works with **Claude Code**, **Cursor**, **ChatGPT**, and any MCP-compatible
client.

## File Watcher

Changes you make in Obsidian sync to the vector index automatically:

| Action | Result |
|--------|--------|
| Add a Session | Indexed |
| Edit a Session | Re-indexed |
| Delete a Session | Removed from index |
| Move a Session | Metadata updated |

Runs inside the MCP server. Detects offline changes on restart.

## Configuration

`mnemos.yaml` in your vault root:

```yaml
version: 1
vault:
  path: "/path/to/your/vault"
sessions:
  languages: [tr, en]
search_backend: chromadb   # or sqlite-vec
```

## Troubleshooting

### Which backend am I on?

```bash
mnemos status
```

The first line tells you — e.g.

    Backend: sqlite-vec (search.sqlite3 · 142 sessions · 8.4 MB)

### ChromaDB index corruption or errors

If Mnemos fails with an HNSW / DatabaseError / segfault-style message from
ChromaDB, the single recovery command is:

```bash
mnemos reindex --backend sqlite-vec
```

This backs up the broken `.chroma/` directory (date-stamped, never
overwritten), updates `mnemos.yaml`, and rebuilds the index from your
vault's `Sessions/` folder. **No memories are lost** — your `.md` files
are the source of truth. Run `--dry-run` first if you want to see the
plan without changing anything.

### Switching back to ChromaDB

Same command, other way around:

```bash
mnemos reindex --backend chromadb
```

Backups are kept under `<vault>/.chroma.bak-YYYY-MM-DD/` and
`<vault>/search.sqlite3.bak-YYYY-MM-DD` — delete them manually when you're
confident the new backend is good.

---

## Migration: v0.x → v1.0

If you ran a previous version of Mnemos:

1. **Existing drawer files preserved.** Files in `<vault>/Mnemos/wings/`
   stay untouched. Mnemos no longer reads them. Delete manually if
   desired.
2. **Run `mnemos identity bootstrap`** to populate the new Identity Layer.
3. **Run `mnemos install-hook --v1`** to update SessionStart hooks
   (atomic, idempotent).
4. **Removed CLI commands:** `mine`, `catch-up`, `migrate`, `import
   claude-code`, `processing-log`. Backend switch is now `mnemos reindex
   --backend X`.
5. **Want the old paradigm?** `pip install mnemos-dev==0.3.3` pins to the
   last v0.x release. The full v0.x source is preserved at branch
   [`legacy/atomic-paradigm`](https://github.com/mnemos-dev/mnemos/tree/legacy/atomic-paradigm).

---

## What's next after v1.0

- **v1.1 — Wikilink resolution intelligence.** Heuristics to merge
  `[[GYP]]` and `[[GYP Energy]]` into a canonical entity, with manual
  override.
- **v1.2 — Cross-vault recall.** Query memory across multiple Obsidian
  vaults (e.g. work + personal) with vault-aware filtering.
- **v1.3 — Obsidian plugin.** A native sidebar in Obsidian: memory
  browser, timeline view, briefing inbox.
- **v2.0 — Self-maintaining memory.** Stale-decision flagging, decay,
  contradiction detection — rebased onto the Sessions graph.

## Benchmarks

Mnemos uses [LongMemEval](https://huggingface.co/datasets/xiaowu0162/LongMemEval)
(500 questions across 54 conversation sessions) for recall measurement.

```bash
pip install mnemos-dev[benchmark]
mnemos benchmark longmemeval              # all 500 questions
mnemos benchmark longmemeval --limit 10   # quick smoke
```

## Contributing

```bash
git clone https://github.com/mnemos-dev/mnemos.git
cd mnemos
pip install -e ".[dev,llm]"
pytest tests/ -v
```

Built from scratch (not a fork) — the v0.x atomic paradigm was inspired by
[MemPalace](https://github.com/MemPalace/mempalace); v1.0's narrative-first
design is original to Mnemos, informed by what we learned testing the
atomic approach to its limit.

## License

MIT — Copyright 2026 Tugra Demirors / GYP Energy
