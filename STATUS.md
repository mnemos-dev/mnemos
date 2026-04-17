# Mnemos — Project Status

**Last updated:** 2026-04-16 (v0.3.0 released to PyPI + GitHub)
**Stable PyPI version:** `v0.3.0` · **Next:** `v0.4.0` (AI Boost / Phase 1)
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
- 🟢 Measured recall: **~90% Recall@5** on a 10-question LongMemEval subset — both backends (ChromaDB and sqlite-vec) verified identical at R@5=0.90 / R@10=0.90 / NDCG@10=0.74 on 2026-04-17. Phase 1 target ≥95%.

### Released — `v0.3.0` First-Run Experience (2026-04-16)

- ✅ `refine-transcripts` Claude Code skill — JSONL → refined Sessions/.md
  with ledger-based resume, zero LLM cost, ships inside the repo via junction/symlink
- ✅ README repositioned around the Claude Code history use case
- ✅ `.mnemos-pending.json` schema + `mnemos.pending` module — atomic
  read/write/upsert API for resumable onboarding, status enum validation,
  schema versioning
- ✅ `mnemos init` 5-phase onboarding flow: intro → discover (Claude Code
  JSONL + vault Sessions/memory/Topics) → [A]ll/[S]elective/[L]ater choice
  → process (curated mined immediately, raw registered as pending with
  refine-skill hint) → hook activation placeholder. Skip/done sources
  honored on re-run via `.mnemos-pending.json`
- ✅ `mnemos import <kind>` command family: `claude-code` (register-only,
  prints refine-skill instructions), `chatgpt` / `slack` (single-file JSON
  exports → mine), `markdown` / `memory` (curated `.md` directories → mine).
  Every import updates `.mnemos-pending.json`.
- ✅ CLI i18n: `mnemos init` intro + onboarding prompts + outcome
  messages localized to TR + EN. Locale resolved from `mnemos.yaml`'s
  `languages` setting (first supported wins; English fallback). Windows
  cp1252 console safe via auto stdout UTF-8 reconfigure.
- ✅ `mnemos install-hook` registers a SessionStart auto-refine hook that
  refines the last 3 unprocessed Claude Code JSONL transcripts in the
  background and mines the vault, without blocking session start. A
  vault-root `.mnemos-hook-status.json` file drives a live statusline;
  a weekly (≥7 day) backlog reminder surfaces via `additionalContext`
  on first-turn AI context. `mnemos init`'s final phase prompts the
  user to install the hook (Y/n, default Y). Subagent JSONLs under
  `/subagents/` are filtered from the picker. `filelock` advisory
  locking prevents overlapping sessions from duplicating work.
- ✅ `mnemos install-statusline` idempotently wires the auto-refine
  progress snippet into `~/.claude/settings.json`. Two modes: append a
  fenced `# --- mnemos-auto-refine-statusline ---` block to a user-owned
  bash/.cmd statusline script (settings untouched) or fresh-install
  `~/.claude/mnemos-statusline.{sh,cmd}` and point `statusLine.command`
  at it. `--uninstall` removes the block (and the owned script +
  `statusLine` key in fresh mode). `.bak-YYYY-MM-DD` backups. `mnemos
  init` prompts for it after the hook step (i18n TR+EN).
- ✅ Auto-refine no longer flickers between sessions: lock-timeout
  returns silently instead of writing a destructive `phase=busy` over
  the lock-holder's `refining 2/3` row, and the SessionStart wrapper
  short-circuits subagent dispatches (`transcript_path` under
  `/subagents/`) so agent-heavy workflows don't spawn fresh bg workers.
  When there's nothing to refine, the bg skips `mnemos mine` and the
  wrapper writes no status at all. Wrapper writes `phase=refining,
  current=0` directly (no `starting` snapshot). The idle render uses new
  `last_outcome` + `last_finished_at` fields to show `mnemos: last
  refine Xm ago · N notes · OK · backlog Y` for 10 minutes (was 30s).
- ✅ Auto-refine no longer re-fires mid-conversation: the wrapper
  whitelists SessionStart `source` values ({"", "startup", "resume",
  "clear"}) so auto-compaction (`source=compact`) and any future
  ephemeral event types short-circuit to exit 0.
  `pick_recent_jsonls(exclude=...)` accepts the current session's own
  `transcript_path` from the hook input, so the in-progress conversation
  is never marked OK in the ledger before it actually ends — fixes the
  silent loss of post-refine turns. Legacy `mnemos-session-mine.py`
  SessionStart entry removed from the author's `~/.claude/settings.json`
  (separate hook that mined raw transcripts; obsolete since 3.7's
  refine-then-mine pipeline).
- ✅ Legacy session-memory deprecation guide: README §"Migrating from
  older session-memory setups" lists exactly which `~/.claude/skills/
  session-memory/` and `~/.claude/hooks/mnemos-*` files an early adopter
  can safely remove now that the auto-refine hook captures everything
  automatically. CONTRIBUTING gains a sibling note so contributors don't
  reintroduce the legacy patterns.
- ✅ New-user pilot validated the README's onboarding works end-to-end
  on a clean throwaway vault (`mnemos init` → mining → search →
  install-hook → install-statusline). Caught one real CLI display bug
  (`mnemos search` showed `wing=?  hall=?` because the formatter read
  the wrong nesting level — fixed and locked down with two regression
  tests in `test_cli_search.py`). Full pilot report:
  [`docs/pilots/2026-04-16-new-user-pilot.md`](docs/pilots/2026-04-16-new-user-pilot.md).
- ✅ PyPI release v0.3.0 — wheel + sdist published to
  <https://pypi.org/project/mnemos-dev/0.3.0/>, GitHub release at
  <https://github.com/mnemos-dev/mnemos/releases/tag/v0.3.0>.
  Pre-release wheel inspection caught a release-blocker (3.10a):
  `install-hook` and `install-statusline` resolved their script and
  snippet paths to `<repo>/scripts/*` — a directory only present in
  dev installs. Fixed by moving the resources into the `mnemos`
  package (`mnemos/auto_refine_hook.py` invoked as `python -m
  mnemos.auto_refine_hook`; `mnemos/_resources/statusline_snippet.{sh,cmd}`
  resolved relatively). Bash-on-Windows (Git Bash MSYS path)
  detection and target-suffix-aware block syntax were folded in too
  so the appended block actually parses on the user's shell.
- ✅ Auto-refine noise filter + truthful status (3.11): picker and
  backlog skip JSONLs with fewer than 3 real user turns
  (`MIN_USER_TURNS`, opt-out with `min_user_turns=0`) — `tool_result`
  messages don't count as turns, so a 1-turn-with-tools session is
  correctly treated as noise. `_run_locked` now reads the ledger
  after each `claude --print` call to count real OK vs SKIP outcomes;
  status JSON gains `last_ok` + `last_skip` fields and a new
  `last_outcome="skip"` value for the all-SKIP case. Statusline
  snippet renders the actual split: "1 note · 2 skipped · backlog 87"
  or "0 notes (3 skipped)" instead of the prior "3 notes · OK" lie
  that surfaced when every pick was a `/clear → mnemos` resume
  session. Fixes the report where backlog grew 150 → 152 across two
  fresh sessions because every fire wasted picks on noise.
- ✅ PID-based active-session exclusion (3.12): each SessionStart
  hook registers its Claude Code parent PID in a marker file under
  `~/.claude/projects/.mnemos-active-sessions/`. Before picking, all
  markers are scanned — live PIDs' transcripts are excluded from
  both picker and backlog. Dead PID markers are cleaned up (session
  closed → transcript becomes available for next hook fire). 24 h
  max-age safety net guards against PID recycling. Solves the
  multi-window scenario (3-4 concurrent Claude Code sessions) where
  the picker could refine an in-progress transcript and silently
  lose later turns.

### Next session starts here

v0.3 tamamlandı + production hardening yapıldı (3.11-3.13). Tüm Claude Code
geçmişi (122 transcript → 52 OK note + 70 SKIP) refine + mine edildi,
backlog **0**. Vault'ta 66 Sessions/*.md notu aranabilir durumda.

v0.4 (AI Boost / Phase 1) sırada — ROADMAP §v0.4.0:

1. **4.1 Phase 1 design spec** — `docs/specs/YYYY-MM-DD-phase1-ai-boost-design.md`
2. **4.2 LLM mining** — Claude API regex'in yakaladığını doğrular + emotional hall
3. **4.3 LLM reranking** — top-50 → top-10 precision boost
4. **4.4 Contradiction detection** — yeni memory eski memory ile çelişiyor mu?
5. **4.5 Benchmark tekrar** — Recall@5 ≥ %95, Recall@10 ≥ %97 hedefi
6. **4.6 PyPI release v0.4.0**

**3.11-3.13 production hardening özeti (2026-04-17):**
- 3.11: `MIN_USER_TURNS=3` noise filter + `last_ok/last_skip` truthful status
- 3.12: PID marker active-session exclusion (multi-window safe)
- 3.12b: mtime fallback (pre-marker sessions) + wrapper status guard
- 3.12c: per-session statusline (`triggering_session_id`) + one-shot simplification
  (Claude Code statusline'ı sürekli poll etmiyor — debug logla kanıtlandı)
- 3.13: 53 backlog batch temizliği (5 paralel subagent triage + 34 `claude --print`
  refine). Final: ledger 122 entry (52 OK / 70 SKIP), backlog 0.

### Practical stats (author's vault, 2026-04-17)

- 277+ drawers across 9 wings, 2-language (TR+EN) regex mining
- Cosine search scores healthy at 0.30–0.70 range
- 66 refined session notes in `Sessions/` (52 OK from 122 processed transcripts)
- Backlog: **0** — all Claude Code JSONL transcripts processed
- Auto-refine hook processes 3 closed transcripts per new session start

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
