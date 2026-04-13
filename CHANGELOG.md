# Changelog

All notable changes to Mnemos are documented here.

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
