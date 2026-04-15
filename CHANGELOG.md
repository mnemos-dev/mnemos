# Changelog

All notable changes to Mnemos are documented here.

## [Unreleased] — v0.3.0 First-Run Experience (in progress)

**Goal:** Make the path from `pip install` to "my AI remembers my history" a single command.

### Added

- **`refine-transcripts` Claude Code skill** — bundled in the repo at `skills/mnemos-refine-transcripts/`, junctioned/symlinked into `~/.claude/skills/`. Reads JSONL transcripts under `~/.claude/projects/`, runs the canonical refinement prompt at `docs/prompts/refine-transcripts.md`, writes high-signal Sessions/<YYYY-MM-DD>-<slug>.md. Ledger-based resume; 5-piece pilot before full batches; zero LLM cost (runs inside the user's Claude Code session). *(commit `a74c10f`)*
- **`.mnemos-pending.json` schema + `mnemos.pending` module** — atomic JSON state at vault root tracking per-source onboarding progress. `PendingSource` (status enum, file counts, last action), `PendingState`, `load`/`save` (atomic via tmp + os.replace) / `upsert_source`. Schema versioning + status enum validation in `__post_init__`. *(commit `0783ba2`)*
- **`mnemos init` 5-phase onboarding wizard** — replaces the legacy "mine vault now?" prompt. Phase 1: intro. Phase 2: discover Claude Code JSONL transcripts + vault `Sessions/`/`memory/`/`Topics/` with file counts and time estimates. Phase 3: `[A]ll` / `[S]elective` / `[L]ater` choice. Phase 4: per-source process loop (curated → mine immediately, raw → register pending with refine-skill hint, skip / later branches). Phase 5: hook activation placeholder. Re-run safe via `.mnemos-pending.json`. *(commit `fc17751`)*
- **`mnemos import <kind>` command family** — `claude-code` (registers JSONL transcripts as pending, prints refine-skill instructions), `chatgpt` / `slack` (single-file JSON exports → mine), `markdown` / `memory` (curated `.md` directories → mine). Every import updates `.mnemos-pending.json`. Shared `_mine_and_record` helper consolidates the in-progress → handle_mine → done flow. *(commit `d9e97a9`)*
- **CLI i18n (`mnemos.i18n`)** — locale-aware string lookup with TR + EN translations for intro, discovery prompts, choice options, per-source prompts, outcomes, and hook placeholder. `t(key, lang, **fmt)` + `resolve_lang(cfg)` API. Locale picked from `mnemos.yaml`'s `languages` setting (first supported wins; EN fallback). Windows cp1252 console safe via auto stdout UTF-8 reconfigure in `main()`. *(commit `0ddaae9`)*
- **README repositioned** around the Claude Code history use case — hero claim "Turn your Claude Code history into a searchable memory palace", refinement skill section, "Why Not Just Raw Transcripts?" comparison table. *(commit `0fd64fc`)*
- **`STATUS.md` external status doc** — single-glance "why does Mnemos exist, what works today, where the roadmap ends up". Linked from README header. *(commit `af6f60f`)*
- **`CONTRIBUTING.md`** — dev setup, ROADMAP discipline, commit style, coding conventions, marker language addition guide, refinement skill workflow, four architectural lines that should not be crossed. *(commit `4eef132`)*
- **Project-level `CLAUDE.md`** — one-word `mnemos` resume protocol for Claude Code. *(commit `655ce11`)*

### Tests

- **+47 new tests** (10 pending, 25 onboarding incl. import-claude-code + path-validation, 14 i18n) on top of v0.2.0's 226. Full suite: ~273 tests.

### Workflow

- **ROADMAP `[ ] → [~] → [x]` discipline** — every task carries a commit hash and date when delivered. Delivered v0.1 + Phase 0 design/plan artifacts archived under `docs/archive/`. *(commits `1394be5`, `1dfeb66`)*

### Remaining v0.3

Auto-refine SessionStart hook (3.7), session-memory skill deprecation (3.8), new-user simulation pilot (3.9), PyPI release (3.10).

---

## [0.2.0] — 2026-04-13 — Phase 0: Foundation

**Goal:** Match MemPalace's 96.6% recall without API calls.

### Added

- **Dual ChromaDB collection** — `mnemos_raw` stores verbatim file content, `mnemos_mined` stores classified fragments. Search merges both via Reciprocal Rank Fusion (RRF).
- **Conversation normalizer** — auto-detects and normalizes 5 chat formats: Claude Code JSONL, Claude.ai JSON, ChatGPT JSON, Slack JSON, and plain text.
- **Exchange-pair chunking** — keeps question + answer together in conversation mining (dynamic max 3000 chars). Non-conversation files use paragraph chunking.
- **Room detection** — 72+ folder/keyword patterns across 13 categories (frontend, backend, planning, testing, security, etc.) replace the old filename-only heuristic.
- **Entity detection** — two-pass heuristic scoring classifies capitalized words as person, project, or uncertain using weighted dialogue/action/code signals. Supports Turkish titles (Bey, Hanim).
- **172 mining markers** — 87 English + 85 Turkish markers across 4 halls (decisions, preferences, problems, events). Previously: 25 EN + 24 TR.
- **Prose extraction** — filters code blocks, shell commands, programming constructs, and low-alpha lines before mining. Prevents code from polluting embeddings.
- **Scoring + disambiguation** — confidence-based hall classification replaces first-match regex. Problems with resolution markers ("fixed", "solved") are reclassified as events (milestones).
- **LongMemEval benchmark** — dataset loader, Recall@K and NDCG metrics, full pipeline runner. Tests against the same dataset as MemPalace for apples-to-apples comparison.
- **`$in` / `$nin` metadata filters** — search across multiple wings (`wing=["A","B"]`) or exclude wings (`exclude_wing="General"`).
- **`--rebuild` flag** — clears mine log and re-mines all sources from scratch.
- **`collection` parameter** — `mnemos_search` tool accepts `"raw"`, `"mined"`, or `"both"` (default).

### Changed

- Mining pipeline rewritten from 4-step regex to 10-step hybrid pipeline.
- `mnemos_drawers` ChromaDB collection renamed to `mnemos_mined`.
- Room detection: folder patterns + keyword scoring instead of filename + H2 heading.
- Entity detection: heuristic two-pass instead of CamelCase-only.

### Benchmark

| Metric | v0.2.0 (Phase 0) | MemPalace | Target |
|--------|:-:|:-:|:-:|
| Recall@5 | 70%* | 96.6% | 95%+ |
| Recall@10 | 70%* | 98.2% | 97%+ |

*Measured on 10/500 questions. Full benchmark pending.

---

## [0.1.0] — 2026-04-12 — Initial Release

### Added

- Palace architecture: Wing > Room > Hall > Drawer hierarchy
- 8 MCP tools: search, add, mine, status, recall, graph, timeline, wake_up
- ChromaDB semantic search with cosine similarity
- SQLite knowledge graph with temporal queries
- L0-L3 memory stack for efficient context loading
- File watcher for automatic Obsidian sync
- Basic regex mining (25 EN + 24 TR patterns)
- External source mining (read-only, one-shot)
- CLI commands: init, mine, search, status
- 51 tests passing
