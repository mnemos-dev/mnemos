# Changelog

All notable changes to Mnemos are documented here.

## [0.3.2] — 2026-04-18 — Palace Hygiene

**Goal:** Clean up nine pipeline bugs that bled into author-vault drawers (wing-name splits, phantom rooms, date-stacked filenames, graph-view ghost nodes, entity/tag pollution) and make `mnemos mine --rebuild` a genuinely atomic, roll-backable operation. The old `--rebuild` was just `mine_log clear + re-mine` — no backup, no index wipe, no rollback. The new one moves `wings/` to `_recycled/wings-<ts>/`, drops + rebuilds both backends' indexes, resets the knowledge graph, verifies the rebuild produced drawers, and restores from backup on any failure.

### Fixed

- **Wing canonicalization** normalizes Turkish diacritics (`ç→c`, `ğ→g`, `ı→i`, `ö→o`, `ş→s`, `ü→u`) and flattens hyphens/underscores before matching so `Satin`, `Satın`, and `Satin-Alma-Otomasyonu` all land in the same wing. Prevents the "same topic, three wings" split that came from inconsistent source-file casing. *(A1, commit `94b624d`)*
- **Lazy hall / wing / room summaries.** `create_wing` and `create_room` no longer pre-create five empty `hall_*/` subdirectories or write `_wing.md` / `_room.md` eagerly. The one hall needed and the two summaries land on first drawer insertion via `add_drawer`. Kills "phantom" rooms (empty halls) and "dead" wings (no summary, no drawer) that polluted the Obsidian graph view. *(A2, commit `590f302`)*
- **`tags[0]` no longer promoted to room name.** Miner previously took the first frontmatter tag and used it as the room, which bloated room names to the full drawer title (`mnemos-—-obsidian-native-ai-memory-palace`). Room now comes from folder/keyword detection only; wing≠room invariant enforced in the pipeline. *(A3, commit `0e72389`)*
- **Drawer filenames use source date, not mining date.** Old code prefixed `YYYY-MM-DD-` using today's date, then the slugged body kept its own date → `2026-04-18-2026-04-13-mnemos-mine-rebuild.md`. Now the slug drops any date token at a word boundary so the prefix is applied once. *(A4, commit `6707010`)*
- **Drawer body template** gains `# <smart-title>` H1 + `> Source: [[<wikilink>]]` blockquote. Obsidian graph view now surfaces real node titles instead of ID prefixes; preview mode shows a readable header instead of a bare chunk. Handles synthetic / manual sources (`synthetic:`, `manual:`) by skipping the wikilink — no more dead `[[unknown]]` links. *(A5 + review fix, commits `13fc74c`, `9532caf`)*
- **Entity hygiene.** Entity list no longer polluted with frontmatter `tags` (previously every mined drawer got `"tags": ["ai", "memory"]` as faux entities). Case-preserve deduplication — `OpenAI` and `openai` collapse to one, keeping the first-seen casing instead of lowercasing everything. *(A6, commit `bbfa1b8`)*

### Changed

- **`mnemos mine --rebuild` is now atomic.** Nine-phase orchestrator in `mnemos/rebuild.py`: resolve sources → build pre-flight plan → dry-run gate → confirm prompt → acquire `.rebuild.lock.flock` → backup wings/index/graph → `SearchBackend.drop_and_reinit()` + `KnowledgeGraph.reset()` → re-mine all sources → verify (drawers > 0 else rollback) → print result. `backend.close()` runs in `finally` so the rollback path can `shutil.rmtree` the storage on Windows without hitting `WinError 32`. Rollback restores all three from `.bak-<ts>` copies. *(B1–B7)*
- **`--rebuild` auto-discovers sources.** Without an explicit path, reads `cfg.mining_sources` from `mnemos.yaml`, falls back to `<vault>/Sessions` + `<vault>/Topics`, raises `RebuildError` with actionable guidance if nothing is configured. `path` argument is now optional when `--rebuild` is used. *(B4, B7)*
- **`--rebuild` UX flags.** `--dry-run` prints the plan (source counts + backup path + existing drawer count) and exits without touching anything. `--yes` skips the `Proceed? [y/N]` prompt. `--no-backup` skips the wings/index/graph backup for users who know what they're doing. *(B5, B7)*
- **Auto-refine hook respects rebuild lock.** If `<vault>/Mnemos/.rebuild.lock.flock` is held, `mnemos/auto_refine_hook.py` silently early-exits (no status write, no bg worker spawn) so concurrent session starts don't fight the orchestrator over wings/ or the search index. Lock probe is non-blocking (50ms timeout) so stale lock files don't block the hook. *(B8, commit `7f30777`)*

### Added

- **`SearchBackend.drop_and_reinit()`** on the abstract base — ChromaDB deletes + recreates both `mnemos_mined` / `mnemos_raw` collections, sqlite-vec drops + recreates `mined` / `raw` / `vec_mined` / `vec_raw` tables via `_init_schema()`. Both backends remain usable for fresh indexing in the same process after the call. *(B1, commit `2059783`)*
- **`Palace.backup_wings(timestamp)`** — atomic `shutil.move` of `wings/` into `_recycled/wings-<ts>/` with `.N` collision suffix so same-second rebuilds never overwrite each other. *(B2, commit `6a9570d`)*
- **`KnowledgeGraph.reset()`** — truncates `triples` + `entities` tables for the rebuild path. *(B3, commit `1c4da1f`)*
- **`mnemos/rebuild.py`** module — `RebuildError`, `_resolve_sources`, `build_plan` + `format_plan`, `rebuild_vault` orchestrator. 17 tests in `tests/test_rebuild.py`: parametrized across both backends for happy-path + drop+reinit, plus dedicated coverage for dry-run no-op, zero-drawer rollback (verified both wings and index restored), lock contention, stale lock recovery, source resolution precedence, error messages. *(B1–B6)*

### Fixed (tests)

- **`tests/test_server.py::test_app_recall`, `tests/test_app_wake_up`, and three `tests/test_stack.py` tests** assumed the old eager summary behavior and checked wing names in recall/wake_up content without any drawer present. Seeded a minimal drawer in each wing (and per room for the L2 case) to trigger A2's lazy summary write. No production code changes. *(commit `509582f`)*

### Distribution-ready memory-source handling (post-pilot fixes)

The real-vault pilot on the author's kasamd vault caught three issues that would bite every distribution user with a Claude Code auto-memory footprint. All three are resolved.

- **`MEMORY.md` index files silently inflated drawer counts.** Claude Code auto-memory folders (`~/.claude/projects/<proj>/memory/`) contain one `MEMORY.md` per folder — pure wikilink index pointing at sibling `user_*.md`, `feedback_*.md`, `reference_*.md` files. Previously the miner treated it as content and produced duplicate-signal drawers. `handle_mine` now filters `MEMORY.md` and any leading-underscore `.md` (summaries mnemos produces itself). *(Part 1, commit `998a529`)*
- **`mnemos import` didn't persist to `mnemos.yaml`.** Every `mnemos import markdown|memory <path>` only wrote `.mnemos-pending.json`, so the very next `mnemos mine --rebuild` silently dropped every imported source. Real-vault pilot lost 102 drawers from five external memory folders this way. `_import_dir` now appends the path (with `mode=curated, external=true`) to `mining_sources` via the new `_append_mining_source` helper — idempotent, preserves every other yaml key, normalizes paths so Windows mixed-slash imports don't duplicate. *(Part 2, commit `e9f3d6d`)*
- **`_resolve_sources` was replacement, not additive.** With Part 2 landed, `mining_sources` would hold the external paths — and the old resolver treated a non-empty `mining_sources` as "use only these", skipping the vault's own `Sessions/` + `Topics/`. Round-trip rebuild on kasamd dropped from 683 drawers to 100 (only the 5 memory folders, Sessions + Topics vanished). The resolver now always auto-discovers the vault's internal source dirs and UNIONs with `mining_sources`, deduped by `os.path.normpath`. Explicit `--path <dir>` still wins as a one-off override. *(post-pilot fix, commit `bb53892`)*

Author-vault final state after the three fixes: 683 drawers (was 670 pre-v0.3.2), 16 wings, 5 mining_sources entries auto-included on every rebuild. Sources `sha256` unchanged — rebuild never modifies source files.


## [0.3.1] — 2026-04-17 — Backend UX


**Goal:** First-class discovery, migration, and corruption recovery for the two vector backends mnemos has been shipping since v0.2. A 2026-04-17 parity benchmark showed ChromaDB and sqlite-vec produce identical recall (R@5=0.90 on LongMemEval 10q, down to the fourth decimal), so the user-facing question is now reliability / environment fit, not quality.

### Added

- **Backend parity baseline** — `benchmarks/longmemeval/runner.py` gained a `backend` parameter. The 2026-04-17 run on both backends produced identical R@5=0.90 / R@10=0.90 / NDCG@10=0.7393 / 8027 drawers. Results under `benchmarks/results/20260417T162632_sqlite-vec_*` + `20260417T162706_chromadb_*`. *(commit `634c3f5`)*
- **`mnemos init` backend prompt** — onboarding asks `[C]hromaDB (default) / [S]qlite-vec:` after the `use_llm` question and before yaml is written, so the first mining pass lands in the chosen backend directly. Eight new i18n keys (TR+EN). Platform-aware hint nudges toward sqlite-vec on Windows + Python 3.14. Re-run idempotent: if `mnemos.yaml` already pins `search_backend`, the picker is skipped. *(commit `3d99c17`)*
- **`mnemos migrate --backend <name>`** — safe switch between ChromaDB and sqlite-vec. Pre-flight plan counts current drawers and source `.md` files, estimates rebuild time (±30% window around 0.46 s/drawer from the parity benchmark). `--dry-run` prints the plan without touching anything. Real run backs up the old storage to a dated sibling (`.chroma.bak-YYYY-MM-DD/`, `search.sqlite3.bak-YYYY-MM-DD`) — never overwrites existing backups (date collision → `.bak-DATE.2`). Updates `mnemos.yaml`, clears `mine_log`, reopens with the new backend and re-mines `Sessions/` + `Topics/` + `memory/`. `--no-rebuild` skips the mining for manual control. Post-run summary warns if the rebuild produced > 20% fewer drawers than before. Same-backend request is a no-op. *(commit `a70f7ed`)*
- **`BackendInitError` wrapper** — new `mnemos/errors.py` with `MnemosError` root. `SearchEngine()` factory catches runtime init failures (HNSW corruption, sqlite DatabaseError, permission issues) and raises a single-line message suggesting `mnemos migrate --backend <other>`. `ValueError` on a bad backend *name* is not wrapped (config typo is a different failure class). CLI `main()` catches `BackendInitError`, prints to stderr, exits 2 — the traceback stays accessible via `__cause__` for future `--verbose` wiring. *(commit `9bb916d`)*
- **`mnemos status` backend summary line** — `SearchBackend.storage_path()` abstract (None when in memory); ChromaBackend points at `.chroma/`, SqliteVecBackend at `search.sqlite3`. `get_stats()` payload gains `storage_bytes` via a shared `_path_size_bytes()` helper that handles file + directory trees. `MnemosApp.handle_status()` now returns a `backend: {name, path, storage_bytes}` block. CLI prints a one-line human summary above the JSON: `Backend: sqlite-vec (search.sqlite3 · 8027 drawers · 42.3 MB)` — directory backends get a trailing slash. `_format_bytes()` renders in KB/MB/GB with one decimal. *(commit `c944dff`)*
- **README Troubleshooting section** — new "Which backend am I on?", "ChromaDB index corruption or errors", and "Switching back to ChromaDB" recipes. Hero paragraph now names both backends and points at the parity benchmark. Architecture diagram updated to note sqlite-vec is a drop-in peer. *(commit `1209457`)*
- **CONTRIBUTING architectural line** — "The backend count stays at two." Third-backend PRs (Qdrant, LanceDB, pgvector) have to show a concrete gap and full `mnemos migrate` parity; most of the time the right answer is improving one of the two we have. *(commit `1209457`)*
- **v0.3.1 spec** — `docs/specs/2026-04-17-v0.3.1-backend-ux-design.md` documents the motivation (including a MemPalace comparison — issues #239, #832, #965, #700, #574 still open there while we ship the fix), the six tasks (3.14a–f), the rollback-on-failure + migration-lock follow-ups, and the key design decisions (no "experimental" label, default stays ChromaDB, two-way migrate, no third backend, ±30% time window, post-rebuild drawer-drop warning). *(commit `2cf3529`)*
- **Clean-vault pilot report** — `docs/pilots/2026-04-17-v0.3.1-backend-pilot.md` documents an end-to-end walk on Windows + Python 3.14.3: init → [S] sqlite-vec → mine demo session → dry-run migrate → real migrate → migrate back → search on rebuilt index → same-backend no-op. All nine steps green; two cosmetic nits (minute window rounds to ~0–0 on tiny vaults; sqlite-vec surface scores are 0.01–0.02 vs ChromaDB's 0.3–0.7) tracked for follow-up. *(commit `d914e84`)*
- **`conftest.py` UTF-8 reconfigure** — test runners on cp1252 Windows consoles now reconfigure `sys.stdout`/`stderr` at import time, matching what `main()` does. Without it, `→` and em-dash glyphs in onboarding copy raised `UnicodeEncodeError` under pytest capsys. *(commit `3d99c17`)*

### Fixed

- **Bulk indexer duplicate drawer IDs** — when the miner emits two drawers with the same slugged ID in a single batch (short repeated user replies like "thats really helpful thanks"), both backends rejected the batch (`DuplicateIDError` on Chroma, `UNIQUE constraint failed on vec_mined` on sqlite-vec). `_bulk_upsert` now collapses duplicates with last-write-wins semantics via a shared `_dedup_by_id` helper. Regression introduced by `97bc9f4` (bulk indexing API) when the single-row `index_drawer` path's idempotent upsert gave way to batched upsert. *(commit `6e48198`)*
- **STATUS/ROADMAP baseline misread** — the previously-quoted "baseline %70 Recall@5" was ChromaDB's pre-optimization first run on 2026-04-13, not a sqlite-vec regression. Corrected to "%90 on both backends" with a note on the optimization history (chunk 3000→800, RRF ×3, source_path metadata). *(commit `634c3f5`)*

### Deferred follow-ups

- `mnemos migrate` rollback-on-failure and migration-lock recovery — happy path is the ship-blocker remover; transactional failure handling + interrupted-migration resumption can be added when a real bug surfaces.
- Dry-run minute estimate reads `~0–0 minutes` on very small vaults (baseline × drawers < 1 min); follow-up could round the floor up or fall back to a seconds string below threshold.
- sqlite-vec search scores hover in the 0.01–0.02 range while ChromaDB is in 0.3–0.7 — rescale / re-normalise during the Phase 1 pass.

### Release

- PyPI: <https://pypi.org/project/mnemos-dev/0.3.1/>
- GitHub release with assets: <https://github.com/mnemos-dev/mnemos/releases/tag/v0.3.1>
- Wheel + sdist: `dist/mnemos_dev-0.3.1-py3-none-any.whl` + `.tar.gz`.

## [0.3.0] — 2026-04-16 — First-Run Experience

**Goal:** Make the path from `pip install` to "my AI remembers my history" a single command.

### Added

- **`refine-transcripts` Claude Code skill** — bundled in the repo at `skills/mnemos-refine-transcripts/`, junctioned/symlinked into `~/.claude/skills/`. Reads JSONL transcripts under `~/.claude/projects/`, runs the canonical refinement prompt at `docs/prompts/refine-transcripts.md`, writes high-signal Sessions/<YYYY-MM-DD>-<slug>.md. Ledger-based resume; 5-piece pilot before full batches; zero LLM cost (runs inside the user's Claude Code session). *(commit `a74c10f`)*
- **`.mnemos-pending.json` schema + `mnemos.pending` module** — atomic JSON state at vault root tracking per-source onboarding progress. `PendingSource` (status enum, file counts, last action), `PendingState`, `load`/`save` (atomic via tmp + os.replace) / `upsert_source`. Schema versioning + status enum validation in `__post_init__`. *(commit `0783ba2`)*
- **`mnemos init` 5-phase onboarding wizard** — replaces the legacy "mine vault now?" prompt. Phase 1: intro. Phase 2: discover Claude Code JSONL transcripts + vault `Sessions/`/`memory/`/`Topics/` with file counts and time estimates. Phase 3: `[A]ll` / `[S]elective` / `[L]ater` choice. Phase 4: per-source process loop (curated → mine immediately, raw → register pending with refine-skill hint, skip / later branches). Phase 5: hook activation placeholder. Re-run safe via `.mnemos-pending.json`. *(commit `fc17751`)*
- **`mnemos import <kind>` command family** — `claude-code` (registers JSONL transcripts as pending, prints refine-skill instructions), `chatgpt` / `slack` (single-file JSON exports → mine), `markdown` / `memory` (curated `.md` directories → mine). Every import updates `.mnemos-pending.json`. Shared `_mine_and_record` helper consolidates the in-progress → handle_mine → done flow. *(commit `d9e97a9`)*
- **CLI i18n (`mnemos.i18n`)** — locale-aware string lookup with TR + EN translations for intro, discovery prompts, choice options, per-source prompts, outcomes, and hook placeholder. `t(key, lang, **fmt)` + `resolve_lang(cfg)` API. Locale picked from `mnemos.yaml`'s `languages` setting (first supported wins; EN fallback). Windows cp1252 console safe via auto stdout UTF-8 reconfigure in `main()`. *(commit `0ddaae9`)*
- **`mnemos install-hook` SessionStart auto-refine hook** — registers a `~/.claude/settings.json` SessionStart entry that refines the last 3 unprocessed Claude Code transcripts in a detached background worker, then mines `<vault>/Sessions/`. Vault-root `.mnemos-hook-status.json` drives a live statusline; weekly backlog reminder via `additionalContext`. Subagent JSONLs filtered. `filelock` advisory locking prevents overlapping sessions from duplicating work. Strips `ANTHROPIC_API_KEY` from the `claude --print` subprocess so it falls back to the user's subscription quota (zero API cost). *(commit `725d569`, hardened in `512e3dd`/`138a4cf`/`4ad8505`/`47f58af`/`96aa07f`)*
- **`mnemos install-statusline` CLI** — idempotently wires the auto-refine progress snippet into `~/.claude/settings.json`. Two modes: append a fenced `# --- mnemos-auto-refine-statusline ---` block to a user-owned bash/.cmd statusline script (settings untouched) or fresh-install `~/.claude/mnemos-statusline.{sh,cmd}` and point `statusLine.command` at it. `--uninstall` removes the block (and the owned script + `statusLine` key in fresh mode). `.bak-YYYY-MM-DD` backups. `mnemos init` prompts for it after the hook step (i18n TR+EN). *(commit `15a21fa`)*
- **README repositioned** around the Claude Code history use case — hero claim "Turn your Claude Code history into a searchable memory palace", refinement skill section, "Why Not Just Raw Transcripts?" comparison table. *(commit `0fd64fc`)*
- **`STATUS.md` external status doc** — single-glance "why does Mnemos exist, what works today, where the roadmap ends up". Linked from README header. *(commit `af6f60f`)*
- **`CONTRIBUTING.md`** — dev setup, ROADMAP discipline, commit style, coding conventions, marker language addition guide, refinement skill workflow, four architectural lines that should not be crossed. *(commit `4eef132`)*
- **Project-level `CLAUDE.md`** — one-word `mnemos` resume protocol for Claude Code. *(commit `655ce11`)*
- **Migration guide for legacy session-memory + `mnemos-session-mine.py` hooks** — README §"Migrating from older session-memory setups" lists the exact files early adopters can remove now that the auto-refine hook captures everything automatically. CONTRIBUTING gains a sibling note so the legacy patterns don't sneak back into the repo. *(commit `77f1b78`)*
- **New-user simulation pilot report** — `docs/pilots/2026-04-16-new-user-pilot.md` documents an end-to-end clean-vault run of the README onboarding (init → mining → search → install-hook → install-statusline), with what worked, what was caught, and what couldn't be tested from inside Claude Code. *(commit `d65384f`)*

### Fixed

- **Auto-refine no longer flickers between sessions** — `auto_refine.run()` returns silently on lock timeout instead of writing a destructive `phase=busy` over the lock-holder's `refining 2/3` row. The SessionStart wrapper short-circuits subagent dispatches (`transcript_path` under `/subagents/`) so agent-heavy workflows don't spawn fresh bg workers. When there's nothing to refine, the bg skips `mnemos mine` and the wrapper writes no status. Wrapper writes `phase=refining, current=0` directly (no `starting` snapshot). The idle render uses new `last_outcome` + `last_finished_at` fields to show `mnemos: last refine Xm ago · N notes · OK · backlog Y` for 10 minutes (was 30s). *(commit `ef69170`)*
- **Auto-refine no longer re-fires mid-conversation** — wrapper whitelists SessionStart `source` values (`{"", "startup", "resume", "clear"}`) so auto-compaction (`source=compact`) and any future ephemeral event types short-circuit. `pick_recent_jsonls(exclude=...)` accepts the current session's own `transcript_path` from the hook input, so the in-progress conversation is never marked OK in the ledger before it actually ends — fixes the silent loss of post-refine turns. *(commit `d6cbeed`)*
- **`mnemos search` CLI showed `wing=?  hall=?` for every hit** — formatter read top-level `r.get("wing")`, but search results carry wing/hall under `metadata`. Caught by the new-user pilot, fixed by reading `r.get("metadata") or {}` first with `?` fallback for ancient indexes. *(commit `d65384f`)*
- **`install-hook` and `install-statusline` were broken under `pip install mnemos-dev`** — both wrote paths to `<repo>/scripts/*` resources that only existed in dev installs. Three changes: (1) `auto_refine_hook.py` moved into the package and invoked as `python -m mnemos.auto_refine_hook` (no filesystem path in `settings.json`); (2) statusline snippets moved to `mnemos/_resources/` so they ship in the wheel; (3) `_parse_existing_target` recognises Git Bash POSIX paths (`/c/Users/...`) and `_build_block` picks bash-vs-cmd syntax from the target script's suffix, not the host OS — fixes a Windows + Git Bash regression where the appended block used `rem`/`set`/`call` inside a `.sh` script.

### Tests

- **+99 new tests** on top of v0.2.0's 226 (10 pending + 25 onboarding + 14 i18n + 9 install-hook + 13 install-statusline + 27 auto-refine behavior + 4 hook-script integration + 2 cli-search formatter). Full suite: 326 passed, 2 skipped.

### Workflow

- **ROADMAP `[ ] → [~] → [x]` discipline** — every task carries a commit hash and date when delivered. Delivered v0.1 + Phase 0 design/plan artifacts archived under `docs/archive/`. *(commits `1394be5`, `1dfeb66`)*

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
