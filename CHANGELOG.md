# Changelog

All notable changes to Mnemos are documented here. For the narrative
version of how the project evolved across paradigms, see
[`HISTORY.md`](HISTORY.md).

## v1.2.1 — Refine-Pipeline Race + Identity Isolation Hot-Fix (2026-04-28)

Spec: [`docs/specs/2026-04-28-v1.2.1-duplicate-refine-race.md`](docs/specs/2026-04-28-v1.2.1-duplicate-refine-race.md)

### Bug

Three independent code paths could call
`claude --print /mnemos-refine-transcripts <jsonl>` concurrently for
the same JSONL: the SessionEnd worker (graceful `/exit` path), the
SessionStart `recall_briefing --catchup` (CASE B X-close fallback),
and the SessionStart `auto_refine_hook` (cross-project backlog
scan). With no per-JSONL coordination, the LLM produced
non-deterministic slugs and two parallel writes either:
- **converged** on the same slug → second write overwrote the first
  → silent data loss (one summary disappeared, the user observed
  "a file briefly appeared then vanished"); or
- **diverged** on different slugs → two `Sessions/<date>-<slug>.md`
  siblings persisted (visible duplicate).

The race also corrupted the ledger TSV (concurrent `open(…, "a")`
appends spliced TAB columns together, producing unparseable lines).

This was a pre-existing v1.1.0 bug; v1.2.0's locale-aware F6.3
empirical smoke surfaced it.

### Fix

**Three hooks coexist by design** — graceful `/exit` fires
SessionEnd; X-close skips SessionEnd and the next SessionStart's
safety nets catch up. Removing any of them would re-open the
X-close coverage gap. The fix makes that coexistence safe:

- **`mnemos/refine_lock.py:claim_jsonl_for_refine(jsonl, ledger)`**
  — pre-check the ledger (fast skip on existing OK/SKIP), acquire
  `filelock.FileLock` at `<ledger-dir>/locks/<stem>.lock` with
  `timeout=0` (fail-fast), recheck the ledger inside the lock so
  workers that waited briefly behind a finisher observe the OK
  entry and bail. Returns a context manager on success, `None` on
  any skip path.
- **All three callers funnel through the gate**:
  `session_end_hook._run_refine`,
  `recall_briefing.run_refine_sync` (catchup path),
  `auto_refine.run` (per-picked-JSONL loop).
- **`mnemos refine-ledger --normalize`** — one-shot CLI to repair
  ledgers corrupted before v1.2.1. Drops malformed lines (not
  exactly 3 TAB columns), dedups same-path entries (OK supersedes
  SKIP, last-seen wins among same-status), optionally drops
  entries whose JSONL no longer exists (`--validate-paths`).
  Atomic via tmp+rename. `--dry-run` previews counts without
  writing.

### Tests

- 11 new tests in `tests/test_refine_lock.py` covering: happy-path
  claim, pre-acquire skip on existing ledger entry, post-acquire
  recheck on race-finished ledger entry, per-stem isolation, 10-
  thread concurrency stress (exactly one winner), and four
  normalize cases (dedup, OK-over-SKIP, TAB-corrupted-line drop,
  missing-path drop) + atomic-write contract.
- 3 new tests in `tests/test_cli_refine_ledger.py` covering the
  CLI happy path, `--dry-run`, and missing-ledger error.
- Total suite: **543 passed**, 2 skipped, 3 deselected (was 529 at
  start of v1.2.1 work; +14 new).

### Identity bootstrap follow-up fixes (same-day)

Empirical bootstrap pilot on kasamd surfaced three more bugs in the
identity pipeline that v1.2.1 also fixes:

- **`identity._invoke_claude_print` did not strip `ANTHROPIC_API_KEY`.**
  Hard-invariant violation — every other claude --print site (auto_refine,
  recall_briefing, session_end_hook) strips the key so the call falls
  through to subscription quota. This one site was missed in v1.0/v1.1
  and silently routed bootstrap + refresh through API credits when the
  user had `ANTHROPIC_API_KEY` set as an env var. Surface symptom:
  `claude --print failed (exit 1):` with empty stderr (after the fix the
  error also includes stderr in the message). Fix: copy env, pop the
  key, pass to subprocess.run.
- **Bootstrap was contaminated by parent cwd + SessionStart hooks.**
  The nested claude --print inherited the parent's cwd, which loaded
  the project CLAUDE.md and let `recall_briefing`'s SessionStart hook
  inject its briefing context. The LLM treated the bootstrap prompt as
  a continuation of the parent dev conversation and emitted a chat
  summary instead of the seven-section profile. Fix:
  `_invoke_claude_print` now sets `MNEMOS_RECALL_HOOK_ACTIVE=1` to
  short-circuit recall_briefing's re-entry, and runs from a fresh
  `tempfile.TemporaryDirectory` so no project context leaks in.
- **`docs/prompts/identity-bootstrap.md` OUTPUT section strengthened.**
  The original "Only the markdown body to stdout" was too subtle;
  rewritten as a four-bullet "strict" contract (no tools, no chat,
  start with `---` frontmatter, fall back to minimal stubs rather
  than refusing).

Plus a small new feature shipped in the same fix wave:

- **`mnemos identity bootstrap --limit N`** — pilot mode that restricts
  input to the most-recent N Sessions. Useful for validating prompt
  quality on a small subset before committing the full vault to a
  10-15 minute LLM call. Default unchanged: read all eligible Sessions.

### Migration path

Users upgrading to v1.2.1 should run once:
```bash
mnemos refine-ledger --normalize --validate-paths
```
This cleans up any corruption already in their ledger. From that
point on, the lock prevents new corruption.

No settings.json changes required — both SessionStart hooks
(`mnemos-auto-refine`, `mnemos-recall-briefing`) and the SessionEnd
hook (`mnemos-session-end`) all stay in place. The lock makes their
coexistence safe. Users with `ANTHROPIC_API_KEY` in their env who
hit the silent bootstrap failure under v1.1 should retry on v1.2.1
— the call now correctly routes through subscription quota.

---

## v1.2.0 — Locale-Aware Output + English-Default Codebase (2026-04-28)

Plan: [`docs/plans/2026-04-28-english-output-strings.md`](docs/plans/2026-04-28-english-output-strings.md)
(implementation pivoted from the plan's "dual-match" strategy to "locale-aware" — the option the plan deferred. See migration path below.)

### Goal

Code, documentation, prompts, and CHANGELOG are uniformly English so a
contributor reading the repo never has to decode Turkish. But at
**runtime** Mnemos respects the user's actual language: a Turkish-speaking
user with Turkish transcripts gets Turkish Session headers, Turkish
identity profile, Turkish briefing labels — that's a feature, not a
defect. An English user gets English everywhere because their
transcripts are English. Mixed/unclear → English default.

### What changed

**Refined Session schema** (`docs/prompts/refine-transcripts.md`)
- Output language rule rewritten as locale-aware: section headers AND
  body match the transcript's dominant language. Schema example shows
  the canonical English form (`## Summary`, `## Decisions`, …) with an
  explicit Turkish translation table (`## Özet`, `## Alınan Kararlar`,
  …) for Turkish transcripts. Mixed/unclear → English default.
- Technical-term preservation rule kept (API, commit, file paths,
  framework names stay English).
- Removed the earlier "Section headers are always English" callout that
  contradicted the goal.

**Identity Layer schema** (`docs/prompts/identity-bootstrap.md`,
`docs/prompts/identity-refresh.md`,
`skills/mnemos-identity-refresh/prompt.md`,
`mnemos/identity.py:_REFRESH_PROMPT_TEMPLATE`)
- Bootstrap canonical schema documented in English with a 7-row
  English ↔ Turkish translation table; rule says match the dominant
  Session language.
- Refresh prompts (both the docs prompt and the in-Python template)
  preserve the existing profile's header language — refresh never
  translates mid-stream. To switch a vault from TR to EN (or vice
  versa), the user runs a clean `mnemos identity bootstrap --force`.
- `_REFRESH_PROMPT_TEMPLATE` rules translated from Turkish to English
  while preserving the same conflict-resolution semantics — the prompt
  body is now English (code/docs), but the section names it references
  follow the existing profile's language.

**Briefing template** (`skills/mnemos-briefing/prompt.md`)
- STEP 5 Synthesize output is locale-aware: 7 bold labels emit in the
  cwd's dominant Session language. Canonical English schema shown with
  a Turkish translation table (`**Current State:**` ↔ `**Aktif durum:**`,
  etc.). Single-language-family rule: never half-EN / half-TR.
- STEP 2A/2B/3 readers explicitly accept BOTH English and Turkish
  Session headers — language-agnostic regex / heuristic match.
- "Bold labels: Match dominant language" is the explicit rule;
  default English when mixed/unclear.

**Cross-check directive** (`mnemos/recall_briefing.py:CROSS_CHECK_DIRECTIVE`)
- Rewritten language-agnostic. Was hard-coded with `"Geçerli kararlar"`
  and `"Revize/iptal edilen kararlar"`; now talks about "any active
  decision listed in the briefing, or any item explicitly marked as
  revised or cancelled" — works against EN, TR, and any future
  language a briefing might carry.

### Tests
- Three TR-back-compat tests prove consumers stay language-agnostic:
  - `test_existing_tr_identity_still_parseable` (`tests/test_identity.py`)
    — `show()` and the wikilink-relevance check both work on a TR
    profile.
  - `test_inject_legacy_tr_briefing_cache_still_works`
    (`tests/test_recall_briefing.py`) — TR briefing cache files inject
    through the directive wrapper unchanged.
  - `tests/conftest.py:sample_session_tr` re-documented as the
    Turkish-content fixture.
- Bulk-flipped 26 fixture occurrences `**Aktif durum:**` →
  `**Current State:**` in `test_recall_briefing.py` (test scaffolding;
  language doesn't affect what's tested).
- Two tests in `test_refine_prompt_v2.py` had stale TR-literal
  assertions left over from the Tier 4 prompt translation
  (pre-existing failures); flipped to EN equivalents.

### Verification
- `pytest tests/ -q` — **529 passed**, 2 skipped, 3 deselected (was
  527 before v1.2.0, +2 new back-compat tests).
- Junction zero-drift — repo == `~/.claude/skills/*/prompt.md` for
  briefing + identity-refresh skills (3 tests pass).
- No-API CI grep — all `ANTHROPIC_API_KEY` references are intentional
  `env.pop()` strip lines or docstrings explaining the strip, no
  client imports.

### Migration path

No migration. Existing Turkish vaults keep producing Turkish output;
new English vaults produce English output; mixed vaults default to
English. The optional `mnemos migrate-headers` helper from the plan's
F7 group was deferred — locale-aware behavior obviates it.

### Strategy pivot from the plan

The original plan (`docs/plans/2026-04-28-english-output-strings.md`)
specified "dual-match": skill prompts emit English-only output;
consumers accept both languages on read. During implementation review
the plan author clarified the goal: code/docs always English, but
runtime output should respect the user's language — which is exactly
the "locale-aware" option the plan §2 deferred. The implementation
pivoted accordingly. Net code-shape impact is small (the prompt
LANGUAGE rules and a few callouts), and all tests still pass without
revision because the prompt files still document the canonical English
schema; only the runtime behavior rule changed.

### Known issue → fixed in v1.2.1

**Duplicate-refine race condition** was discovered during the
F6.3 empirical smoke (single `/exit` produced two
`Sessions/<date>-<slug>.md` files for the same JSONL). The race
predates v1.2.0; v1.2.1 ships the fix on the same day. See the
v1.2.1 entry above for the full bug + remedy.

---

## v1.1.0 — SessionEnd-Driven Memory (2026-04-27)

Spec: [`docs/specs/2026-04-26-v1.1.0-sessionend-driven-memory-design.md`](docs/specs/2026-04-26-v1.1.0-sessionend-driven-memory-design.md)
Plan: [`docs/plans/2026-04-26-v1.1.0-sessionend-driven-memory.md`](docs/plans/2026-04-26-v1.1.0-sessionend-driven-memory.md)

### Issue 1 — Refine pipeline configurability + Settings TUI
- New `mnemos settings` numbered TUI for unified config (20 fields + refinement progress).
- Configurable refine batch size (`refine.per_session`, default 3).
- Configurable refine direction (`refine.direction`, default `newest`).
- Configurable noise floor (`refine.min_user_turns`, default 3).
- `mnemos init` now includes a quota dialog (subscription cost reality + per-session config) before writing yaml.

### Issue 2 — Identity bootstrap + auto-refresh
- Identity bootstrap eligibility gate (`identity.bootstrap_threshold_pct`, default 25%).
- Auto-refresh from SessionEnd worker (`identity.auto_refresh`, `identity.refresh_session_delta`, `identity.refresh_min_days`).
- New skill `mnemos-identity-refresh` for delta-based identity update.
- Bootstrap + refresh prompts gain GOOD/BAD/EDGE classification examples + final self-check.

### Issue 3 — Briefing readiness gate
- New config: `briefing.readiness_pct` (default 60%) — below threshold the SessionStart inject path is silent (avoids anchoring the AI on partial history).

### Issue 4 — Smart-layered revision-aware briefing
- Briefing prompt rewritten as v3: previous brief as anchor + all-cwd Sessions decision-only + recent 5 sessions full body.
- Revision detection: contradicting decisions explicitly marked in "Revize/iptal edilen kararlar".
- Token budget raised to 25K hard cap with priority-driven truncation.

### Issue 5 — In-session briefing usage
- New config: `briefing.show_systemmessage` (default true) — visible "Mnemos: <cwd> briefing loaded · N sessions" line at session start.
- New config: `briefing.enforce_consistency` (default true) — prepends a cross-check directive to additionalContext so Claude pauses when the user contradicts an established decision.

### Architectural foundation
- **NEW:** SessionEnd hook + detached worker (`mnemos.session_end_hook`).
  - Hook returns under 100 ms (fits Claude Code's 5 s X-close grace window).
  - Worker uses `CREATE_BREAKAWAY_FROM_JOB` (Windows) / `start_new_session` (POSIX) to survive Claude Code termination.
  - 3-stage sequential pipeline: refine THIS transcript -> regen brief -> identity refresh check.
- **NEW:** SessionStart sync fallback for missed SessionEnd cases (mid-stream X-close, kill -9).
- **NEW:** CASE A first-visit vault-aware sync brief — if the vault already has Sessions for the cwd, brief inline instead of staying silent.
- **NEW:** `mnemos install-end-hook` CLI (atomic install/uninstall, idempotent, surgical).
- **NEW:** `mnemos/readiness.py` helpers — `count_eligible_jsonls`, `count_refined_sessions`, `compute_readiness_pct`, `per_cwd_readiness`.

### Hard invariant
**No Anthropic API calls anywhere.** All LLM operations route through `claude --print` subscription quota. CI grep enforces. `_child_env()` strips `ANTHROPIC_API_KEY` from every spawned subprocess.

### Bug fixes
- Re-entry guard placement regression coverage carried over from the v1.0 `a19cfb9` lesson — the SessionEnd worker has its own guard test ensuring `--worker` mode bypasses `HOOK_ACTIVE_ENV`.
- Briefing junction `~/.claude/skills/mnemos-briefing` re-pointed at the v1.1 worktree path (post-migration cleanup) so the canonical-prompt zero-drift test no longer skips.

### Test coverage
- 65+ new tests; suite pass count grows from 455 (v1.0 baseline) to 527 with v1.1 G1-G10 implemented (G12 empirical validation pending).

## v1.0.0 — Narrative-First Pivot (2026-04-25)

### Breaking changes
- Atomic-fragmentation paradigm ("drawer" mining) removed. Mnemos no longer
  produces or indexes drawer fragments.
- CLI: `mnemos mine`, `mnemos catch-up`, `mnemos migrate`, `mnemos import
  claude-code`, `mnemos processing-log` removed (legacy invocations print
  a friendly v1.0 removal message).
- MCP: `mnemos_mine` and `mnemos_add` tools removed. `mnemos_search` no
  longer accepts `collection="mined"` or `"both"` (warns and falls back to
  `raw`).
- Wing/Hall/Room hierarchy retired. `mnemos_recall(level="L1"|"L2")` returns
  a deprecated marker.

### Added
- **Identity Layer** (`<vault>/_identity/L0-identity.md`) — persistent user
  profile, bootstrapped from existing Sessions, evolves via incremental
  refresh.
- `mnemos identity {bootstrap,refresh,rollback,show}` CLI commands.
- Briefing skill produces 3-layer narrative (Identity 3K + cwd Sessions 8K +
  cross-context wikilink expansion 4K, hard cap 15K).
- Refine prompt v2 produces tag + wikilink hybrid (`tags: [proj/x, tool/y,
  person/z, file/r, skill/s]` + prose `[[X]]`).
- `mnemos reindex` for backend switch and index recovery (replaces
  `mnemos migrate`).
- `mnemos install-hook --v1` atomic idempotent installer with stale-hook
  graceful failure shim.

### Refactored
- `mnemos_graph(entity)` and `mnemos_timeline(entity)` now query Obsidian
  wikilink graph instead of SQLite triple store. Tool signatures unchanged.

### Removed code
- Mining pipeline (9 modules, ~3K LOC).
- Knowledge graph SQLite store (`mnemos/graph.py`).
- ~200 drawer-related tests.
- `mnemos-mine-llm` and `mnemos-compare-palaces` skills.

### Migration
See [README "Migration: v0.x → v1.0"](README.md#migration-v0x--v10).

### Pre-v1.0 paradigm preservation
- Branch `legacy/atomic-paradigm` and tag `v0.4.0-archived` preserve full
  v0.x source. Pin `pip install mnemos-dev==0.3.3` for stable v0.x.

## [0.3.3] — 2026-04-19 — Post-v0.3.2 cleanup

**Goal:** Close four deferred follow-ups flagged during the v0.3.1 and v0.3.2 pilots so the tree is green and user-visible friction is gone before Phase 1 work starts. No new features — only fixes to UX, test-suite reliability, and cross-backend score presentation.

### Fixed

- **`mnemos migrate` dry-run time estimate.** Vaults with fewer than ~130 drawers used to display `~0–0 minutes` because both endpoints of the estimate rounded to zero. New `MigrationPlan.format_estimate()` switches to seconds below the minute threshold (`~2–3 seconds`, `~29–54 seconds`) and floors the lower bound at 1 second so a tiny vault still shows a real number. Units are singular/plural-correct. *(commit `4ba52e4`)*
- **sqlite-vec score display parity with ChromaDB.** `_l2_to_cosine_sim` is now `_l2_to_score` and uses the linear form `1 - L2 / 2` instead of the cosine form `1 - L2² / 2`. Both are monotonic in L2 distance so ranking is unchanged — the 2026-04-17 LongMemEval parity benchmark (R@5=0.90 on both backends) still holds. The change fixes the pilot-report nit: sqlite-vec scores sat around 0.016 for representative "unrelated" content while ChromaDB's backend showed 0.3–0.7 for the same material. The linear form places both backends in the same visual band so users don't mistake 0.016 for a broken index. *(commit `4ba52e4`)*
- **Test-suite timeout.** `test_write_without_close_can_lose_hnsw_segments` spawns a subprocess that writes 500 drawers + both backends' schemas — on Python 3.14 + Windows that now exceeds the old 300 s wall. Bumped the subprocess timeout to 600 s and tagged the test `@pytest.mark.slow` so it runs alongside its two already-tagged siblings. *(commit `4ba52e4`)*

### Added

- **`MigrateError` + atomic `mnemos migrate` rollback.** The rebuild step in `migrate()` is wrapped in a `BaseException` guard — if mining on the new backend crashes (or the user Ctrl+C's), the old backend's storage is moved back from its `.bak-<date>/` sibling, `mnemos.yaml` is reverted to the pre-migrate backend, and the partial new-backend storage is deleted. Raises `MigrateError` with a single-line "rolled back — still on `<old>`" message that the CLI surfaces via `sys.exit(2)`. `_backup_mine_log` replaces `_clear_mine_log` so the log comes back with the rollback instead of being lost. *(commit `4ba52e4`)*
- **Migration lock (`.migrate.lock.flock`).** `migrate()` acquires a `filelock.FileLock` in the palace directory with a 0.1 s non-blocking acquire; a concurrent migrate on the same vault now raises `MigrateError` with a "Another mnemos migrate is already running" message and doesn't touch any files. Lock is advisory / OS-held, so a crashed process releases it automatically — no stale `.flock` file blocks the next run. *(commit `4ba52e4`)*
- **`[tool.pytest.ini_options]` section in `pyproject.toml`.** Registers the `slow` marker, enables `--strict-markers` so typos fail loudly, and sets default `addopts = "-m 'not slow'"` so `pytest tests/` finishes in ~5 min without flaky long-running subprocesses. Run the full set with `pytest tests/ --override-ini="addopts="` or `pytest -m slow`. *(commit `4ba52e4`)*

### Tests

- **+7 new unit tests** across `tests/test_migrate.py`: four `format_estimate` edge cases (sub-minute seconds mode, sub-second floors at 1, unit flip at the 60 s boundary, large-vault minutes); one rollback-on-rebuild-failure; one rollback-restores-mine-log; one lock-blocks-concurrent. Full suite: **463 passed, 2 skipped, 3 deselected** (the `slow`-tagged durability trio).

### Release

- PyPI: <https://pypi.org/project/mnemos-dev/0.3.3/>
- GitHub release with assets: <https://github.com/mnemos-dev/mnemos/releases/tag/v0.3.3>

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
