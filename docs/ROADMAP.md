# Mnemos Roadmap

**Single source of truth.** Update this file as you implement, then commit.
Older `docs/specs/2026-04-*` and `docs/plans/2026-04-*` files are historical
archive; if they conflict, this file wins.

**Last updated:** 2026-04-26 (v1.0.0a1 alpha shipped + bg-catchup hotfix; v1.1 design + 55-task plan ready)
---

## Version status

| Version | Title | Status | PyPI |
|---|---|---|---|
| v0.1.0 | First Breath | ✅ | ✅ |
| v0.2.0 | Full Memory (= Phase 0 Foundation) | ✅ | ✅ |
| v0.3.0 | First-Run Experience | ✅ | ✅ |
| v0.3.1 | Backend UX (discovery + migrate + recovery) | ✅ | ✅ |
| v0.3.2 | Palace Hygiene (pipeline fixes + atomic rebuild) | ✅ | ✅ |
| v0.3.3 | Post-v0.3.2 cleanup (migrate rollback+lock, score parity, slow-tests) | ✅ | ✅ |
| ~~v0.4.0~~ | ~~AI Boost / Phase 1~~ — superseded by v1.0 narrative-first pivot | 🗄️ archived | — |
| **v1.0.0a1** | **Narrative-first pivot (atomic-fragmentation dropped, Sessions = unit, Identity Layer)** | ✅ shipped 2026-04-26 | ⏸ deferred |
| **v1.1.0** | **SessionEnd-driven memory (refine+brief+identity-refresh worker, settings TUI, briefing v3, readiness gates, in-session cross-check)** | **🔄 plan ready** | — |
| v1.2.0 | Polish + LongMemEval benchmark (R@5 ≥ 93% baseline, JSONL-direct identity bootstrap?) | ⏸ | — |
| v0.5.0 | Automation / Phase 2 — superseded by v1.1 SessionEnd hook | 🗄️ archived | — |
| v0.6.0 | Community & Ecosystem (Obsidian plugin, multi-language markers, demo video) | ⏸ | — |

**v1.1.0 spec:** [`docs/specs/2026-04-26-v1.1.0-sessionend-driven-memory-design.md`](specs/2026-04-26-v1.1.0-sessionend-driven-memory-design.md)
**v1.1.0 plan:** [`docs/plans/2026-04-26-v1.1.0-sessionend-driven-memory.md`](plans/2026-04-26-v1.1.0-sessionend-driven-memory.md) (55 TDD tasks, 13 groups)

---

## v1.1.0 — SessionEnd-Driven Memory 🔄 *(plan ready 2026-04-26)*

13 task groups, 55 tasks. Subagent-driven implementation recommended.

### Tasks (group-level checkpoints; full TDD step list lives in the plan)

- [ ] **G1** — Config schema foundation (5 tasks) — schema_version + nested RefineConfig/BriefingConfig/IdentityConfig + atomic save w/ backup
- [ ] **G2** — Refine pipeline configurability (6 tasks) — pick_jsonls(cfg), direction newest/oldest, min_user_turns from config, caller updates
- [ ] **G3** — Identity eligibility helpers + bootstrap gate (5 tasks) — readiness pct, threshold gate, --force flag, refresh trigger from config
- [ ] **G4** — Identity refresh skill (3 tasks) — `mnemos-identity-refresh` scaffold + junction + zero-drift test
- [ ] **G5** — Briefing prompt v3 (3 tasks) — smart-layered (anchor + all-decisions + recent 5) + revision-aware rewrite + tests
- [ ] **G6** — SessionStart updates (5 tasks) — readiness gate, systemMessage, cross-check directive, sync fallback, vault-aware first-visit
- [ ] **G7** — SessionEnd hook + worker (6 tasks) — module skeleton, detached spawn w/ CREATE_BREAKAWAY_FROM_JOB+fallback, 3-stage worker, re-entry guard regression, hook entry schema, stale-hook detection
- [ ] **G8** — install-end-hook CLI (4 tasks) — atomic install, --uninstall, argparse wiring, roundtrip test
- [ ] **G9** — Settings TUI (7 tasks) — render_menu + validators + apply_field_change + cmd_settings + per-cwd readiness + progress display + i18n
- [ ] **G10** — Init flow integration (3 tasks) — refine quota dialog, install-end-hook prompt, i18n
- [ ] **G11** — Documentation (5 tasks) — README hero+quota, CHANGELOG, identity-bootstrap v2 prompt, CONTRIBUTING no-API rule, CI grep
- [ ] **G12** — Empirical validation (3 tasks) — farcry/procuretrack/mid-stream X-close smoke on real kasamd vault. **BLOCKING for G13.**
- [ ] **G13** — Release prep (4 tasks) — version bump, build, pre-release inspection, PyPI+GitHub publish (DEFERRED — user-triggered)

### Hard invariants (spec §2)

- ❌ **NO Anthropic API calls anywhere** — `claude --print` subscription only, `_child_env()` strips API key, CI grep enforces
- 📁 Obsidian master, vault is source of truth
- ⚛️ Idempotent hooks, atomic file ops
- 🔓 SessionEnd worker survives parent termination (CREATE_BREAKAWAY_FROM_JOB)
- 🚫 No silent failure on user-actionable conditions

### Success criteria

- [ ] All G1-G11 task-level tests pass (target ≥520 total, was 455)
- [ ] No-API CI grep passes (zero violations)
- [ ] G12 empirical smoke 3 cwd × full lifecycle on kasamd green
- [ ] User reviews + approves implementation before G13 release

---

## v1.0.0a1 — Narrative-First Pivot ✅ *(2026-04-26)*

Atomic-fragmentation paradigm dropped. Sessions/.md = canonical memory unit.
Identity Layer scaffold introduced. Mining pipeline (~3K LOC + ~200 tests)
deleted. 33 commits + 2 hotfixes on main. Tag `v1.0.0a1` pushed; PyPI publish
deferred per staged rollout strategy.

**Hotfix (2026-04-26):** `recall_briefing.py` re-entry guard moved to AFTER
`--catchup`/`--brief-and-cache` arg parsing. Pre-fix: bg subprocess inherited
HOOK_ACTIVE_ENV=1 → guard at top of main() blocks --catchup → no cache ever
written for any cwd since v1.0 went live. Fix + 2 regression tests, full suite
455 pass. Empirically validated by producing fresh procuretrack briefing cache
(4128B, 18 sessions) — pre-fix had no cache file at all.

(Full release notes: STATUS.md "v1.0.0a1 alpha shipped" section + git log)
---

## v0.1.0 — First Breath ✅ *(2026-04-12)*

- [x] Core MCP tools: search, add, mine, status
- [x] Regex-only mining (LLM optional)
- [x] ChromaDB + Obsidian dual storage
- [x] File watcher (sync)
- [x] CLI: init, mine, search, status
- [x] TR + EN language support
- [x] PyPI publish (mnemos-dev)
- [x] GitHub org (mnemos-dev)

## v0.2.0 — Full Memory / Phase 0 Foundation ✅ *(2026-04-13 → 04-14)*

Goal: reach MemPalace-level recall (96%+) without using any API.

- [x] Second wave tools: recall, graph, timeline, wake_up
- [x] L0-L3 memory stack
- [x] Knowledge graph (temporal triples, SQLite)
- [x] Dual ChromaDB collection (raw + mined), RRF merge
- [x] Metadata filter `$in` (multiple wings/rooms)
- [x] 5 conversation format normalizers (Claude Code JSONL, Claude.ai, ChatGPT, Slack, plain text)
- [x] Exchange-pair chunking (question+answer together)
- [x] Room detection — 72+ folder/keyword patterns, 13 categories
- [x] Heuristic entity detection (person/project)
- [x] 172 markers (87 EN + 85 TR) — 4 halls (decisions/preferences/problems/events)
- [x] Scoring + disambiguation (min_confidence=0.3, problem→milestone)
- [x] Prose extraction (code line filtering)
- [x] LongMemEval benchmark harness
- [x] `_recycled` soft-delete mechanism
- [x] sqlite-vec alternative backend (cosine score)
- [x] Case-insensitive wing resolution
- [x] Bulk indexing API (10-25x faster mining)

Benchmark: **90% Recall@5** on 10 questions (Phase 1 target 95%+).
The initial run (2026-04-13) was 70% before optimization; chunk 3000→800 + RRF
fetch ×3 + source_path metadata pushed it to 90% the same day. On 2026-04-17,
sqlite-vec and ChromaDB backends were run separately — identical numbers to
the fourth decimal (R@5=0.90, NDCG@10=0.7393, 8027 drawers). Backend choice
doesn't affect recall; Phase 1 will target the mining pipeline.

---

## v0.3.0 — First-Run Experience 🔄 *(started 2026-04-15)*

**Problem:** Phase 0 is technically ready, but there's no "download → run →
benefit" path for external users. v0.3 opens that door.

**Main decision — selective refinement:**

| Source | Refine? |
|---|---|
| JSONL transcripts, email export, PDF | YES (noisy/raw) |
| Curated `.md` with frontmatter (memory, Sessions, Topics) | NO |

Refinement = a user-triggered skill that runs inside a Claude Code session.
Mnemos itself calls no LLM APIs. Zero cost, zero dependency.

### Tasks

- [x] **3.1 refine-transcripts skill** *(commit `a74c10f`, 2026-04-15)*
  - `skills/mnemos-refine-transcripts/SKILL.md` + canonical prompt reference
  - Ledger (`state/processed.tsv`) — OK+SKIP recorded, resume works
  - Subagent filter ON by default, `--include-subagents` opt-in
  - 0-turn fast-path, collision guard, pilot protocol (>5 → confirm after first 5)
  - 5-transcript pilot: 2 OK (GYP GTIP/TPAO kota), 3 SKIP
  - Junction setup (`~/.claude/skills/` → repo) zero-drift

- [x] **3.2 README reposition** *(commit `0fd64fc`, 2026-04-15)*
  - Hero: "Turn your Claude Code history into a searchable memory palace"
  - Quick Start gets skill install (mklink/ln -s) + pilot flow
  - "Why Not Just Raw Transcripts?" comparison table
  - Roadmap section v0.3=First-Run

- [x] **3.3 `.mnemos-pending.json` schema** *(commit `0783ba2`, 2026-04-15)*
  Single JSON at the vault root. Schema:
  ```json
  {
    "version": 1,
    "sources": [
      {
        "id": "claude-code-jsonl",
        "path": "~/.claude/projects",
        "kind": "raw-jsonl",
        "status": "in-progress",   // pending|in-progress|done|skipped-by-user|error
        "discovered_at": "ISO-8601",
        "total": 244,
        "processed": 5,
        "last_action": "pilot-accepted"
      }
    ]
  }
  ```
  Files: `mnemos/pending.py` (new) — read/write/append API. All
  `init` + `import` commands use this module.

  **Delivered:** `mnemos/pending.py` + `tests/test_pending.py` (10 tests,
  all passing). Public API: `PendingSource`, `PendingState`, `load()`,
  `save()` (atomic via tmp+replace), `upsert_source()`, `pending_path()`.
  Status enum validated in `__post_init__`; unknown schema version raises.

- [x] **3.4a `mnemos init` onboarding core** *(commit `fc17751`, 2026-04-15)*
  The existing init only does vault scaffolding. New 5-phase flow (user spec, 2026-04-15):

  1. **Phase 1 — Introduction** — what Mnemos is, how it works; first run + every run
  2. **Phase 2 — Discovery** — scan quietly, report file count + estimated time
  3. **Phase 3 — Decision** — three-way `[A]ll / [S]elective / [L]ater` choice
  4. **Phase 4 — Processing** — resumable, update pending.json after each file
  5. **Phase 5 — Hook activation** — *(happens in 3.7; placeholder in 3.4a)*

  3.4a scope (first slice): all 5 phases for **JSONL + curated-md** sources.
  Other formats (ChatGPT/Slack/Claude.ai/Gemini) get added to discovery in 3.5.
  i18n (TR+EN) moved to 3.4b. Real hook activation lands in 3.7.

  Files: `mnemos/cli.py` (`cmd_init` extension), new
  `mnemos/onboarding.py` discover/classify/process.

- [x] **3.4b CLI i18n infrastructure + TR+EN onboarding strings** *(commit `0ddaae9`, 2026-04-15)*
  Locale-aware string system for Phase 1 introduction and Phase 3 prompts.
  Falls to the first language in `mnemos.yaml`'s `languages` list; default `en`.

  **Delivered:** `mnemos/i18n.py` (dict-based, 17 keys × {en, tr}),
  `t(key, lang, **fmt)` + `resolve_lang(cfg)`. In CLI, `cmd_init` →
  `_print_intro/_run_onboarding/_apply_decision/_mine_and_record/`
  `_print_hook_placeholder` all take a `lang` parameter.
  Windows cp1252 console fix: `sys.stdout.reconfigure(
  encoding='utf-8', errors='replace')` at the top of `main()`. 14 new tests, all green.

- [x] **3.5 `mnemos import <source>` subcommand family** *(commit `d9e97a9`, 2026-04-15)*
  Extends discovery to ChatGPT/Slack/Claude.ai/Gemini formats
  (added to `onboarding.py`). Incremental path forward for users who chose
  `mnemos init [L]`.
  Adding sources after init:
  - `mnemos import claude-code [--projects-dir PATH] [--limit N] [--refine]`
    — gives the user the refine skill prompt (Mnemos calls no LLM) +
    orchestrates `mnemos mine Sessions/`
  - `mnemos import chatgpt <export.json>`
  - `mnemos import slack <export.json>`
  - `mnemos import markdown <dir>`
  - `mnemos import memory <dir>` (Claude memory folders)
  Every command updates `.mnemos-pending.json`.
  Files: `mnemos/cli.py` (argparse subparser), new
  `mnemos/importers/` module.

- [x] **3.6 CONTRIBUTING.md** *(commit `4eef132`, 2026-04-15)*
  Git workflow, branch naming, running tests, skill development, how to
  add new languages/markers. Plus: architectural "no-cross" lines
  (Obsidian master, no LLM in mnemos itself, dual-collection separation,
  junction/symlink drift forbidden).

- [x] **3.7 SessionStart auto-refine hook** *(commit `725d569` + hardening `96aa07f`, 2026-04-16)*
  SessionStart hook + `scripts/auto_refine_hook.py` wrapper. Hook command:
  `python <script> --vault <path>` (forward-slash path on Windows, no
  `cmd /c` wrapper). The script accepts the `--vault` arg or the `MNEMOS_VAULT`
  env. Background: for the last 3 JSONLs, `claude --print --dangerously-skip-permissions
  "/mnemos-refine-transcripts <path>"` (detached, `filelock`-guarded, `ANTHROPIC_API_KEY`
  is stripped from the subprocess env → subscription auth). Then `python -m
  mnemos.cli --vault <v> mine <v>/Sessions`. Statusline reads
  `.mnemos-hook-status.json` live; weekly backlog reminder is conveyed to the AI
  via `additionalContext`. Subagent JSONLs (`/subagents/`) are filtered out in
  the picker. `mnemos install-hook` is idempotent, backs up settings.json, and
  identifies the entry via the `_managed_by: mnemos-auto-refine` field.
  `mnemos init`'s last phase installs the hook with user consent.
  Verified in real use: 6 session JSONLs were auto-refined + mining completed
  in the user's kasamd vault, with 0 API credits spent.

  **Bug chain fixed during pilot:**
  - `725d569` — mine command was launching the MCP server via `python -m mnemos` → `python -m mnemos.cli` + `--vault`; subagent JSONL filter; Windows `CREATE_NO_WINDOW`
  - `512e3dd` — marker `# mnemos-auto-refine\n<cmd>` format failed in cmd.exe → `_managed_by` sibling field
  - `138a4cf` — nested `\"path\"` inside `cmd /c` was being mangled by cmd.exe quote stripping → inner quotes removed
  - `4ad8505` — `claude --print` was burning API quota due to `ANTHROPIC_API_KEY` in env → strip from subprocess env → subscription auth
  - `47f58af` — `cmd /c` wrapper was opening an interactive cmd via the Claude Code dispatch → direct `python <script> --vault <path>` call, no shell wrapper
  - `96aa07f` — Claude Code's Windows hook dispatch was mangling backslash escapes (eating `\P\m\s`) → forward slash normalization

  **Canonical docs:**
  - Spec: [`docs/specs/2026-04-15-v0.3-task-3.7-auto-refine-hook-design.md`](specs/2026-04-15-v0.3-task-3.7-auto-refine-hook-design.md)
  - Plan + pilot outcomes: [`docs/plans/2026-04-15-v0.3-task-3.7-auto-refine-hook-implementation.md`](plans/2026-04-15-v0.3-task-3.7-auto-refine-hook-implementation.md)

- [x] **3.7c Statusline UX + auto-refine behavior fixes** *(commit `ef69170`, 2026-04-16)*

  **Problem (5 root causes from the 3.7 live test):**
  1. **Destructive `busy` write (the real bug)** — when `auto_refine.run()` can't
     grab the lock, it writes `phase=busy`; this overwrites the lock-holding
     worker's `refining 2/3` line in the shared status file. Statusline flicker:
     `refining → busy → refining → busy → idle → busy → idle`. The user sees
     flicker on every subagent dispatch.
  2. **Subagent fires SessionStart** — `matcher: ""` triggers on every event,
     including subagent kicks. Every Agent dispatch (Explore, Plan, etc.)
     spawns a new bg worker → mostly lock-fails → writes `busy`.
  3. **Mining happens even with no work** — even when `picked=[]`, bg runs
     `mnemos mine Sessions/` (holds the lock 3-5 s). Even empty subagent
     dispatches create contention.
  4. **`phase=idle` 30s TTL may be broken on Git Bash** — `date -d "$updated_at"`
     ISO offset parsing fails in some environments; fallback diff=0 → "go quiet
     after 30s" never fires. The spec's desired "Xm ago, N notes" message
     requires `last_outcome` + `last_finished_at` fields.
  5. **`phase=starting` snapshot is misleading** — the wrapper writes
     `starting 0m1s`, then bg writes `refining` 1-2 s later; the first render
     looks stuck on `starting`.

  **Solution (behavior + cosmetic):**
  - `mnemos/auto_refine.py`:
    - If `run()` can't acquire the lock, **exit silently without touching the
      status file** (the lock holder is already keeping it current; the
      destructive `busy` write was bug #1)
    - `_run_locked()` **skips** the `mnemos mine` call when `picked=[]`
      (avoids needless lock-holding and CPU). Reminder marking still happens.
    - `write_status` gains optional `last_outcome` (`ok` / `noop`) +
      `last_finished_at` fields (so idle can carry last-round meta-info)
  - `scripts/auto_refine_hook.py`:
    - **Subagent filter**: if the hook stdin JSON's `transcript_path` contains
      `/subagents/`, immediately `exit 0` (no bg spawn, no status write). Fixes #2.
    - If `picked=[]` and `reminder=False`, the wrapper exits **without writing
      the status file or spawning bg** (screen stays quiet on empty dispatches)
    - When `picked>0`, write `phase=refining, current=0, total=N` directly
      instead of `phase=starting` (fixes #5)
  - `scripts/statusline_snippet.{sh,cmd}`:
    - idle TTL 30s → 600s (10 min)
    - idle render: when `last_outcome` + `last_finished_at` exist, use
      `mnemos: last refine Xm ago · N notes · OK` format
    - `busy` message: `mnemos: other session active` (backward-compatible;
      new code no longer writes it, but kept for old status files)

  **Files:**
  - `mnemos/auto_refine.py` — lock-silent, skip-empty-mining, last_outcome
  - `scripts/auto_refine_hook.py` — stdin JSON parse, subagent filter, no-op skip,
    refining-without-starting
  - `scripts/statusline_snippet.{sh,cmd}` — TTL + idle format + busy wording
  - `tests/test_auto_refine.py` — lock-fail silent, skip-mining, last_outcome
  - `tests/test_auto_refine_hook_script.py` — subagent skip, no-op skip
  - `docs/specs/2026-04-15-v0.3-task-3.7-auto-refine-hook-design.md` — §5.1 updated

- [x] **3.7d Stop mid-conversation re-firing** *(commit `d6cbeed`, 2026-04-16)*

  **Problem:** 3.7c closed the subagent contention, but the hook is still
  firing multiple times within a single conversation. Hook log: 3-5 refine
  rounds per hour. Two remaining root causes:
  1. **Automatic compaction fires SessionStart with `source=compact`.**
     This is a mid-conversation event — the transcript isn't done yet, and
     refining is both unnecessary and harmful (it writes "OK" to the ledger
     and the rest gets ignored forever). Only events with "new session"
     semantics should refine (`startup`, `resume`, `clear`).
  2. **The in-progress conversation's own JSONL falls into the picker.**
     `pick_recent_jsonls` sorts by mtime → the newest file is usually this
     conversation's live transcript. Refining and writing it to the ledger
     means the rest of the conversation is never mined. The hook input's
     `transcript_path` already says this; it must be passed to the picker
     as "exclude".

  **Solution:**
  - `mnemos/auto_refine.py` — add `exclude: set[str] | None` parameter to
    `pick_recent_jsonls`. Skip listed paths (str-normalized). We don't use
    exclude in `compute_backlog` — the user wants to see "X files still
    waiting".
  - `scripts/auto_refine_hook.py`:
    - **Source whitelist**: if the hook stdin's `source` is `compact` (or any
      future ephemeral source), immediately `exit 0`. Whitelist: `{"", "startup",
      "resume", "clear"}`. Unknown sources default-skip (deliberate
      forward-compat; prevents undesired behavior when a new Claude Code event
      shows up).
    - Pass `transcript_path` as `pick_recent_jsonls(exclude={...})`.
  - **Bonus cleanup**: the legacy `mnemos-session-mine.py` SessionStart entry
    still in `~/.claude/settings.json` (overlaps with mnemos-auto-refine, does
    raw mine — redundant since the new refine flow). Remove from
    settings.json + delete the related `~/.claude/hooks/mnemos-*.{py,json,log,lock}`
    files (with user consent).

  **Files:**
  - `mnemos/auto_refine.py` — `pick_recent_jsonls(exclude)` param
  - `scripts/auto_refine_hook.py` — source whitelist, exclude self-transcript
  - `tests/test_auto_refine.py` — exclude param tests
  - `tests/test_auto_refine_hook_script.py` — source filter, self-exclude integration
  - `~/.claude/settings.json` — remove legacy SessionStart entry (manual, with backup)

- [x] **3.7b `mnemos install-statusline` CLI** *(commit `15a21fa`, 2026-04-16)*

  **Problem:** the 3.7 hook writes `<vault>/.mnemos-hook-status.json` and the
  repo ships `scripts/statusline_snippet.{sh,cmd}`, but users have to manually
  add them to their own `statusline-command.sh`. Without automation,
  "nobody sees it" → no automatic feedback.

  **Solution:** a new command following the `install-hook` pattern. Flow:
  1. Read the `statusLine.command` field from `~/.claude/settings.json`.
  2. If there's an existing statusline script (`bash <path>` format):
     - Append 3 lines idempotently to that script:
       ```bash
       # --- mnemos auto-refine statusline (managed by mnemos install-statusline) ---
       export MNEMOS_VAULT="<resolved-vault>"
       source "<repo>/scripts/statusline_snippet.sh"
       ```
     - Use the "managed by" marker to skip on re-run.
  3. If there's no statusline at all:
     - Create `~/.claude/mnemos-statusline.sh` (just calls our snippet).
     - Add `statusLine: {type: "command", command: "bash ~/.claude/mnemos-statusline.sh"}` to `settings.json`.
  4. Backup: `.bak-YYYY-MM-DD` for `settings.json` and the target script (like install-hook).
  5. `--uninstall` option: find + remove the snippet block by marker; if a
     separate script was created, delete it and remove the `statusLine` config.

  **Files:**
  - `mnemos/install_statusline.py` (new) — pure logic, testable
  - `mnemos/cli.py` — `install-statusline` subparser + handler
  - `tests/test_install_statusline.py` — appending to existing script,
    creating from scratch, idempotency, uninstall, settings.json preservation
  - `mnemos init` optional: after the hook prompt, ask "install statusline
    too? [Y/n]" (i18n: `statusline_install_prompt/done/declined`)

  **Acceptance criteria:**
  - User with an existing statusline: runs `install-statusline` → in the
    next Claude Code session, auto-refine progress shows under the chatbox
    and all previous statusline behavior is preserved.
  - User with no statusline: `install-statusline` sets up a minimal
    statusline that shows only the mnemos progress line.
  - Re-run is a no-op (already-installed status).

- [x] **3.8 session-memory skill deprecation** *(commit `77f1b78`, 2026-04-16)*
  The legacy `~/.claude/skills/session-memory/` (manual SAVE-on-keyword skill) +
  `~/.claude/hooks/mnemos-session-mine.py` (raw-transcript miner) are now
  redundant — the refine-transcripts skill produces the same information
  more comprehensively and tool-noise-free on every SessionStart.

  **Delivered:**
  - Added a `### Migrating from older session-memory setups` section
    to the README: which files can be deleted + how to remove the old
    SessionStart entry from `~/.claude/settings.json` (with attention
    to the managed-by marker).
  - Added a `#### Legacy hooks early adopters may still have` subheading
    to the CONTRIBUTING SessionStart hook section (contributor perspective:
    don't re-add these hooks to the repo).
  - README roadmap line is current: 3.7b/3.7c/3.7d/3.8 are in the delivered list.
  - The author's own `~/.claude/settings.json` had its legacy entry
    already removed under 3.7d; the 4 related files were deleted
    (with user consent). README has the instructions for external users.

- [x] **3.9 New-user simulation pilot** *(commit `d65384f`, 2026-04-16)*
  In a clean throwaway vault (`C:/Temp/mnemos-pilot-2026-04-16/`) +
  isolated fake HOME (`C:/Temp/mnemos-pilot-home-2026-04-16/`),
  ran the entire onboarding flow from the README from scratch:

  - **Init wizard** (piped stdin: `en\n\nA\nn\nn`) → `mnemos.yaml`,
    `Mnemos/` palace, `.mnemos-pending.json`. Discovery found 341 JSONL +
    1 curated `.md`, [A]ll choice mined the curated file
    (8 drawers + 24 entities, wing `pilot-vault-test` from frontmatter).
  - **Search + status + re-mine** (`files_scanned: 0, skipped: 1`) → all green.
  - **install-hook** & **install-statusline** against the isolated HOME:
    install / re-run → `already-installed` / `--uninstall` → clean
    cleanup. Both produced a `.bak-2026-04-16` backup.

  **Pilot bug**: `cmd_search` formatter was reading `r.get("wing")`;
  drawers carry it under `metadata.wing` — so all CLI search output
  showed `wing=?`. Fix: read from `r.get("metadata") or {}`, with `?`
  fallback for old indexes. New: `tests/test_cli_search.py` (2 tests).
  Pilot report: [`docs/pilots/2026-04-16-new-user-pilot.md`](pilots/2026-04-16-new-user-pilot.md).

  **What we didn't pilot** (with reasons in the pilot report):
  PyPI install (waiting for 3.10), live SessionStart fire (can't be
  launched from inside Claude Code; 3.7 was already verified in
  production), refine-skill execution (requires interactive Claude Code).

- [x] **3.10a Package-data fix (release-blocker)** *(commit `de47085`, 2026-04-16)*
  Found while inspecting the v0.3.0 wheel: `mnemos/cli.py:_hook_script_path()`
  and `mnemos/install_statusline.py:_repo_snippet_path()` point to
  `scripts/auto_refine_hook.py` + `scripts/statusline_snippet.{sh,cmd}` at the
  repo root via `Path(__file__).resolve().parent.parent / "scripts"`. The
  wheel only ships the `mnemos/` package (`packages = ["mnemos"]`), so
  `scripts/` is not in the wheel. For `pip install mnemos-dev` users,
  `install-hook` + `install-statusline` write paths that don't exist →
  `python: can't open file` on SessionStart.

  **Fix:**
  - `scripts/auto_refine_hook.py` → `mnemos/auto_refine_hook.py`
    (importable module). `install-hook` now writes `python -m mnemos.auto_refine_hook
    --vault X` (no filesystem path, just module invocation).
  - `scripts/statusline_snippet.{sh,cmd}` → `mnemos/_resources/...`.
    `_repo_snippet_path()` returns `Path(__file__).resolve().parent / "_resources" /
    name` (resolved from inside the package, works in both dev and pip install).
  - In `pyproject.toml`, hatch `force-include` or `include` setting to ship
    non-py files under `_resources/*`.
  - The author's current `~/.claude/settings.json` carries the old path; refresh
    after the fix with `mnemos install-hook --uninstall && install-hook`.

- [x] **3.10 PyPI release v0.3.0** *(2026-04-16)*
  - PyPI: <https://pypi.org/project/mnemos-dev/0.3.0/>
  - GitHub release: <https://github.com/mnemos-dev/mnemos/releases/tag/v0.3.0>
  - Tag: `v0.3.0` (annotated). Wheel + sdist attached as release assets.

- [x] **3.11 Auto-refine noise filter + truthful status reporting** *(commit `a86c57a`, 2026-04-16)*

  **Problem (user report, post-3.10 live use on 2026-04-16):**
  The hook fires, the statusline shows "refining 1/3 · 0m1s · backlog 151"
  then "last refine 4m ago · 3 notes · OK · backlog 152" — but backlog is
  growing 150 → 151 → 152, never shrinking. Investigation found two
  orthogonal root causes:

  1. **The picker grabs the newest 3 by mtime.** In the author's flow, the
     newest JSONLs are usually `/clear → mnemos` resume sessions (16-30 lines,
     1-2 user turns). The refine-skill correctly SKIPs them, but every new
     session adds +1 JSONL → backlog never shrinks, the picker keeps cycling
     noise. Pilot numbers confirm it: ledger 6 OK / 44 SKIP.
  2. **The statusline is lying.** `last_outcome="ok"` is set whenever
     `picked` is non-empty — "3 notes · OK" actually means "3 JSONLs visited
     (all SKIP, 0 markdown written)". The user feels "no work was done".

  **Solution:**
  - `mnemos/auto_refine.py`:
    - New `MIN_USER_TURNS = 3` constant + `_count_user_turns(path)` helper
      (parses the Claude Code JSONL, doesn't count `tool_result` messages
      as real user turns — count cap 500 lines, cheap)
    - `pick_recent_jsonls` and `compute_backlog` get a `min_user_turns: int =
      MIN_USER_TURNS` kwarg → short transcripts are invisible to both pick
      and backlog (default 3, `0` to opt out)
    - `_latest_outcome_for_path(ledger, path)` helper — reads the ledger's
      latest entry (append-only, latest wins)
    - After each refine, `_run_locked` uses this helper to count OK/SKIP delta;
      writes `last_ok` + `last_skip` to status
    - Final `last_outcome`: `picked=[]` → "noop"; `ok>0` → "ok";
      `picked>0 but ok=0` → **"skip"** (new state, closes the lie)
    - `write_status` accepts optional `last_ok`, `last_skip` kwargs; if unset,
      they're omitted from the JSON (backward compatible)
  - `mnemos/_resources/statusline_snippet.{sh,cmd}`:
    - Idle render uses `last_ok`/`last_skip` when present:
      - `ok>0 & skip>0` → "X notes · Y skipped"
      - `ok>0 & skip=0` → "X notes"
      - `ok=0 & skip>0` → "0 notes (Y skipped)"
    - Falls back to the old `total + outcome` render when these fields are
      missing in older status JSON formats

  **Test (TDD):**
  - `tests/test_auto_refine.py`: `_count_user_turns` (minimal, tool_result
    exclude, missing file, malformed lines), picker turn-filter (newest
    short skipped, threshold boundary, 0=disable), backlog turn-filter,
    write_status outcome counts (set + omit), `_run_locked` ledger delta
    (mixed OK+SKIP, all SKIP → outcome=skip, all OK → outcome=ok, empty
    → outcome=noop). 12 new tests + the existing `_write_jsonl` helper
    got a `user_turns=3` default (without breaking existing tests)
  - `tests/test_auto_refine_hook_script.py`: `_run_hook` helper produces a
    3-turn JSONL (since the filter is also active in the subprocess)

  **Impact:**
  - Backlog reflects the real "processable" count (in the test vault
    ~150 → likely ~30, most drop out via the noise filter)
  - 30-60s × 3 empty `claude --print` calls (consuming subscription quota)
    on every session start are gone
  - Statusline shows what was actually done: "0 notes (3 skipped)" →
    the user sees the system is working and understands the picker
    picked the wrong files

- [x] **3.12 PID-based active-session exclusion** *(commit `136f49b`, 2026-04-17)*
  **3.12b hardening** *(commit `b7e9f40`, 2026-04-17)*:
  - mtime fallback (`RECENTLY_MODIFIED_SECONDS = 1800`): for JSONLs without a
    PID marker (sessions opened before the 3.12 deploy), if mtime < 30 min
    then "probably open" → drop from picker + backlog. The live test gap
    proven: this conversation's JSONL was marker-less and got refined by a
    new session.
  - Wrapper status guard: if the status file shows `phase=refining/mining`,
    the wrapper does NOT write a new `refining 0/3` → won't overwrite the
    running worker's status. Observed in live testing as "0/3 stuck".
  - `read_status_phase(vault)` helper → used by the hook wrapper.

  **Problem:** 3.7d only excludes its own transcript (self). With 3-4
  concurrent Claude Code windows open, the picker may pick and refine
  other open sessions' live JSONLs — they get marked OK on the ledger
  while the transcript is still being written, and subsequent turns
  silently disappear. The mtime heuristic (5 min idle → considered closed)
  is unreliable: the user switches between windows, can stay idle while
  thinking.

  **Solution — PID marker files:**
  - `~/.claude/projects/.mnemos-active-sessions/<session-id>.json` marker:
    `{pid, transcript_path, started_at}`
  - The hook wrapper grabs Claude Code's PID via `os.getppid()` → writes the marker
  - Before the picker runs, scan all markers:
    - PID alive (`kernel32.OpenProcess` / `os.kill(0)`) → exclude transcript
    - PID dead → delete marker, transcript becomes pickable again
    - Marker > 24h → PID recycling guard, delete
  - `get_active_transcript_paths()` → picker `exclude=` + `compute_backlog(active_paths=)`
  - Backward compatible: `active_paths=None` = old behavior (existing tests not broken)

  **Test (TDD):**
  - `_is_pid_alive` (own PID=True, dead PID=False)
  - `register_active_session` (marker file is created)
  - `get_active_transcript_paths` (live=included, dead=cleaned, stale=cleaned, empty=no crash)
  - `pick_recent_excludes_active_sessions` (works with the existing exclude param)
  - `compute_backlog(active_paths=)` (active excluded, None=backward compat)

- [x] **3.12c Per-session statusline + one-shot simplification** *(commit `a04a1dc` + `1f7e296`, 2026-04-17)*
  Claude Code calls the statusline command once at session start (no
  continuous polling — proven via debug logs). The snippet was rewritten
  accordingly: elapsed timer, running tally, and stale-idle TTL were
  removed. Added `triggering_session_id` — only the session that triggered
  the refine sees the result; other windows stay silent. Live test
  observation: the "last refine 4m ago" line in another window made the
  user think "it's refining itself". No longer.

- [x] **3.13 Backlog batch cleanup** *(2026-04-17)*
  All 53 unprocessed transcripts were processed in one go. 5 parallel
  subagents triaged (OK/SKIP decision), then 34 OK files were refined in
  parallel (3-way) with `claude --print --dangerously-skip-permissions`.
  19 SKIPs were written to the ledger. Final: 122 ledger entries
  (52 OK, 70 SKIP), backlog **0**, 66 .md notes under Sessions/.

### Success criteria

- [x] External user can install a working Mnemos in a clean vault by following the 5 README steps *(verified by 3.9 pilot)*
- [x] `mnemos init` discovers 244 JSONL transcripts and can offer pilot + import *(3.4a)*
- [x] `.mnemos-pending.json` resume works — no need to start over if a session breaks *(3.3 + 3.4a)*
- [x] `mnemos import` supports all 5 formats *(3.5: claude-code/chatgpt/slack/markdown/memory)*
- [x] Skill install (junction/symlink) is documented + tested *(3.6 CONTRIBUTING + 3.1 SKILL.md)*
- [x] Auto-refine hook is production-hardened: noise filter, PID exclusion, mtime fallback, per-session statusline, backlog 0 *(3.11-3.13)*

---

## v0.3.1 — Backend UX ✅ *(2026-04-17)*

**Problem:** the code supports two vector backends (ChromaDB + sqlite-vec).
The 2026-04-17 parity benchmark gave identical numbers down to the fourth
decimal (R@5=0.90). But external users have no idea this alternative exists:
`mnemos init` doesn't ask, the README has a single parenthetical, and a
ChromaDB corruption produces a cryptic traceback. MemPalace (42K stars) is
in the same boat — their repair command (#239) + Qdrant (#700) + LanceDB
(#574) PRs are still open.

We've already shipped sqlite-vec; the work is helping users discover it,
migrate safely, and find their way through errors.

**Canonical spec:**
[`docs/specs/2026-04-17-v0.3.1-backend-ux-design.md`](specs/2026-04-17-v0.3.1-backend-ux-design.md)

### Tasks

- [x] **3.14c BackendInitError wrapper** *(commit `9bb916d`, 2026-04-17)*
  `mnemos/errors.py` (new) + factory wrapper in `mnemos/search.py`. Catches
  ChromaDB HNSW load or sqlite-vec DB open errors and prints a "migrate
  --backend X" suggestion to the user. CLI main() catches in one place +
  stderr + exit 2. `tests/test_backend_errors.py` 7 tests; full search+miner+pending
  suite 59 pass.

- [x] **3.14e `mnemos status` backend info** *(commit `c944dff`, 2026-04-17)*
  `SearchBackend.storage_path()` abstract (default None) + override in both backends.
  `get_stats()` output gains `storage_bytes` (shared `_path_size_bytes()` helper).
  `handle_status` returns a `backend: {name, path, storage_bytes}` block. CLI
  prints a `Backend: <name> (<path> · N drawers · X MB)` line before the JSON.
  9 new tests + 50 pass full suite, real-vault smoke verified.

- [x] **3.14b `mnemos migrate --backend X` command** *(commit `a70f7ed`, 2026-04-17)*
  `mnemos/migrate.py` (new) + CLI subparser. Pre-flight plan (drawer +
  source file count + time estimate, ±30% margin), `--dry-run`, backup
  (`.chroma.bak-YYYY-MM-DD` / `search.sqlite3.bak-YYYY-MM-DD`, second migrate
  same day uses `.bak-DATE.2` suffix), yaml update, mine_log clear, rebuild,
  drawer-drop warning (>20% drop → "backup preserved"). 8 tests + real-vault
  dry-run smoke verified. Rollback-on-failure + migration-lock recovery
  recorded as follow-up work.

- [x] **3.14a `mnemos init` backend prompt** *(commit `3d99c17`, 2026-04-17)*
  Backend picker after the `use_llm` prompt (before yaml is written) — so the
  first mining goes to the right backend. `_ask_backend_choice` + platform sniff
  `_resolve_backend_hint` (extra line on Windows+Py3.14). 8 new i18n keys (EN+TR).
  Re-run idempotency: doesn't ask if `search_backend` is already in yaml.
  conftest.py UTF-8 stdout reconfigure added (fixes unicode glyph crash on
  cp1252 Windows test runners). 18 new tests + 63 pass full suite.

- [x] **3.14d README Troubleshooting + hero tweak** *(commit `1209457`, 2026-04-17)*
  README hero paragraph explicitly mentions both backends + parity benchmark reference.
  New "Troubleshooting" section with 3 recipes: `mnemos status` (which backend),
  corruption → `migrate --backend sqlite-vec` (+ `--dry-run`), reverting.
  Architecture diagram shows sqlite-vec as a peer. New architectural line in
  CONTRIBUTING: "backend count stays at two" + a high-bar criterion for any
  3rd-backend PR.

- [x] **3.14f Pilot + release v0.3.1** *(commit `d914e84`, 2026-04-17)*
  Clean-vault pilot ([`docs/pilots/2026-04-17-v0.3.1-backend-pilot.md`](pilots/2026-04-17-v0.3.1-backend-pilot.md))
  full flow green. Version bump `0.3.0 → 0.3.1`, wheel + sdist build successful
  — critical files (migrate, errors, auto_refine_hook, _resources) all in the
  wheel (3.10a package-data bug did not recur). Annotated tag `v0.3.1` pushed,
  GitHub release at <https://github.com/mnemos-dev/mnemos/releases/tag/v0.3.1>
  (with wheel + sdist assets). PyPI upload handed to the user.

### Success criteria

- [ ] External user sees the backend choice in `mnemos init`, doesn't have to
      open `mnemos.yaml` by hand
- [ ] On ChromaDB corruption, the error message shows the
      `mnemos migrate --backend sqlite-vec` command, user recovers via copy-paste
- [ ] `mnemos status` output has a backend line — a user asking for support
      can see which backend they're on
- [ ] Migrate works in both directions (chromadb ↔ sqlite-vec), backups stay safe
- [ ] README Troubleshooting gives the problem + solution in a single paragraph

---

## v0.3.2 — Palace Hygiene ✅ *(2026-04-18)*

**Problem:** nine pipeline bugs piled up in the author's vault — the same
topic getting split across three different wings (diacritic + dash), empty
hall folders cluttering the graph view, `tags[0]` getting promoted to room
name (rooms with title-length names), double-date prefixes in drawer
filenames, graph nodes showing only IDs (no titles), entity list polluted
with frontmatter tags. And `mnemos mine --rebuild` was named "atomic"
while actually only doing `mine_log clear + re-mine` — no backup, no
index wipe, no rollback. Open to data loss on partial failure in a large
vault.

**Canonical spec:**
[`docs/specs/2026-04-18-v0.3.2-palace-hygiene-design.md`](specs/2026-04-18-v0.3.2-palace-hygiene-design.md)

### Tasks

- [x] **A1 Wing canonicalization (TR diacritic + delimiter normalize)** *(commit `94b624d`, 2026-04-18)*
- [x] **A2 Lazy hall / `_wing.md` / `_room.md` create** *(commit `590f302`)*
      — Empty wings and phantom room folders are no longer created.
- [x] **A3 Remove `tags[0]` → room promotion, flatten wing≠room** *(commit `0e72389`)*
- [x] **A4 Source-date filename + word-boundary slug** *(commit `6707010`)*
- [x] **A5 Drawer body H1 title + source wikilink** *(commit `13fc74c`,
      review fix `9532caf` — `[[unknown]]` link is dropped for
      synthetic/manual sources)*
- [x] **A6 Entity hygiene — no tags, case-preserve dedup** *(commit `bbfa1b8`)*
- [x] **A2 follow-up test fix** *(commit `509582f`)* — `test_app_recall`,
      `test_app_wake_up`, and three `test_stack.py` tests assumed A2's old
      eager `_wing.md` behavior; seeded each wing with a minimal drawer
      to trigger the lazy summary.
- [x] **B1 `SearchBackend.drop_and_reinit()`** *(commit `2059783`)*
      — Abstract method + ChromaDB + sqlite-vec implementations. The backend
      can be reused in the same process after rebuild.
- [x] **B2 `Palace.backup_wings(timestamp)`** *(commit `6a9570d`)*
      — Atomic `shutil.move`. The `.N` collision suffix prevents two
      rebuilds from clashing in the same second.
- [x] **B3 `KnowledgeGraph.reset()`** *(commit `1c4da1f`)*
- [x] **B4 `mnemos/rebuild.py` — `_resolve_sources` + `RebuildError`** *(commit `729eea4`)*
      — Explicit path > `cfg.mining_sources` > auto-discover `Sessions/`
      + `Topics/` > `RebuildError`.
- [x] **B5 `build_plan` + `format_plan`** *(commit `b70a935`)*
      — Source count + backup path + current drawer count for dry-run.
- [x] **B6 `rebuild_vault` orchestrator** *(commit `86a915b`)*
      — Nine phases: resolve → plan → dry-run gate → confirm → lock →
      backup (wings + index + graph) → `drop_and_reinit` + `graph.reset`
      → re-mine → verify → rollback on failure.
- [x] **B7 CLI wire — `mnemos mine --rebuild` + `--dry-run`/`--yes`/`--no-backup`** *(commit `85e301c`)*
      — `path` is now optional (works with auto-discover via `--rebuild`).
- [x] **B8 Auto-refine hook `.rebuild.lock.flock` early-exit** *(commit `7f30777`)*
      — When the orchestrator holds the lock, the hook exits silently.
      The 50 ms non-blocking probe doesn't get blocked by stale lock files.
- [x] **Code review fix-up** *(commit `d290de8`)* — `backend.close()` and
      `graph._conn.close()` are now in `try/finally` → so on Windows the
      rollback path can run `shutil.rmtree(storage_path)` (open handles
      were causing `WinError 32`). `_resolve_sources` is no longer called
      twice (`plan["sources_resolved"]` is carried through). `test_rebuild_happy_
      path` was parametrized to cover ChromaDB end-to-end rebuild
      (dir backup vs sqlite-vec's file backup — first time). New
      stale-lock recovery test added. 17 tests, all green.
- [x] **C3 Version bump + CHANGELOG** *(commit `37244d7`)*
- [x] **C4 STATUS + ROADMAP up to date** *(commit `09c4451`)*
- [x] **C1 Light pilot** *(commits `bf60a6a` + `6c80e8d` + `1097ccb`)*
      — Unit tests green, dry-run against kasamd matched plan (81 sources,
      670 drawers), single-file smoke caught two A4/A5 regressions
      (double-date filename + `# # Title` H1) which were fixed.
- [x] **C2 Real vault rebuild + memory re-import + round-trip** *(commits
      `998a529` + `e9f3d6d` + `0abfd7e` + `bb53892`)*
      — kasamd rebuilt end-to-end. Caught and fixed three
      distribution-ready bugs (MEMORY.md noise, import-not-persisted,
      `_resolve_sources` replacement vs additive). Final: 683 drawers
      (NET +13 over pre-v0.3.2), 16 wings, 5 `mining_sources` entries
      auto-included in every rebuild forward.
- [ ] **C5 Build, tag, PyPI, GitHub release**

### Success criteria

- [x] `mnemos mine --rebuild` atomic — wings backup, index drop + reinit,
      graph reset, verify, rollback on failure
- [x] Auto-refine hook and rebuild orchestrator don't run concurrently
      (FileLock-based mutual exclusion)
- [x] Pipeline hygiene — TR diacritic normalize, lazy summaries, no
      tags→room promotion, source-date filename, H1+wikilink body,
      case-preserve entity dedup
- [x] Both backends had `rebuild_vault` tested end-to-end (ChromaDB
      dir backup + sqlite-vec file backup)
- [x] Real vault rebuild successful (C2 — kasamd pilot 683 drawers)

---

## v0.3.3 — Post-v0.3.2 cleanup ✅ *(2026-04-19)*

**Problem:** four small items were deferred to the CHANGELOG during the
v0.3.1 + v0.3.2 pilots — some cosmetic (score display, dry-run estimate),
some user-experience-blockers (no migrate rollback, no concurrent migrate
protection, durability test stuck on a 300s timeout). Closed in a single
commit to leave the tree green before Phase 1.

### Tasks

- [x] **Migrate rollback-on-failure + migration lock** *(commit `4ba52e4`)*
      `MigrateError`, `.migrate.lock.flock` (filelock, advisory), rebuild
      fail → automatic restore of backup+yaml+mine_log + partial new-backend
      cleanup. 3 new tests (rollback, mine_log restore, lock contention).
- [x] **Dry-run estimate edge case** *(commit `4ba52e4`)*
      `MigrationPlan.format_estimate()` — sub-60s seconds mode, 1s floor.
      4 new tests (seconds, sub-second floor, minute boundary, large vault).
- [x] **sqlite-vec score rescale** *(commit `4ba52e4`)*
      `_l2_to_cosine_sim` → `_l2_to_score`: `1 - L2/2` (linear, monotonic,
      same 0.3–0.7 visual band as ChromaDB). Ranking and benchmark recall
      identical — only the surface display changed.
- [x] **Durability test deselect + slow marker** *(commit `4ba52e4`)*
      `[tool.pytest.ini_options]` in `pyproject.toml` + `slow` marker
      register + `--strict-markers` + default `addopts = "-m 'not slow'"`.
      `test_write_without_close_can_lose_hnsw_segments` tagged + subprocess
      timeout 300→600s.
- [x] **PyPI release v0.3.3** — <https://pypi.org/project/mnemos-dev/0.3.3/>,
      GitHub release at <https://github.com/mnemos-dev/mnemos/releases/tag/v0.3.3>.

---

## v0.4.0 — AI Boost / Phase 1 🔄 *(started 2026-04-19)*

**Goal:** skill-first LLM augmentation. We offer the user two orthogonal
axes (mine-mode × recall-mode), each either script (no-API, deterministic)
or skill (`claude --print` inside a Claude Code session, uses subscription
quota, no API package). The pilot orchestrator produces 10 sessions in
two palaces in parallel; the user decides on their own data.

**The original API-based 4.2-4.4** (Claude SDK mining + rerank +
contradiction) **is cancelled** — the skill pattern reaches the same goal
more cleanly. Rerank dissolved into skill-recall; contradiction was deferred
to v0.5 hygiene.

**Canonical spec:**
[`docs/specs/2026-04-19-phase1-ai-boost-design.md`](specs/2026-04-19-phase1-ai-boost-design.md)

### Tasks

- [x] **4.1 Write Phase 1 design spec** *(2026-04-19)*
  `docs/specs/2026-04-19-phase1-ai-boost-design.md` — skill-first reframe,
  4-combo architecture, pilot orchestrator, settings TUI, items deferred
  to v0.5.
- [x] **4.2 Skill-mine + pilot orchestrator** *(2026-04-19 → 20, shipped, live in kasamd)*
  - [x] **4.2.1** `skills/mnemos-mine-llm/` skill + canonical prompt *(commit `c7d6c58`)*
  - [x] **4.2.2** `mnemos/pilot.py` orchestrator + `mnemos mine --pilot-llm` *(commit `e300a2c`, 28+3 tests)*
  - [x] **4.2.3** `skills/mnemos-compare-palaces/` skill + prompt *(commit `777d076`)*
  - [x] **4.2.5** `mnemos pilot --accept <script|skill>` command *(commit `777d076`, 7+3 tests)*
  - [x] **4.2.6 Real-vault pilot** *(2026-04-19, kasamd 3 sessions)* — it
        worked, skill-mine drawer quality clearly above script's; produced
        4 operational findings. Report:
        [`docs/pilots/2026-04-19-v0.4-phase1-real-vault-pilot.md`](pilots/2026-04-19-v0.4-phase1-real-vault-pilot.md)
  - [x] **4.2.7 Ledger reliability fix** *(2026-04-19)* — orchestrator
        `count_drawers_for_session` fallback: when the ledger is empty,
        read the drawer frontmatter `source:` field, count session drawers
        from the filesystem + "recovered from filesystem" OK outcome.
        Hardened the ledger-append reflex in SKILL.md ("🔴 REQUIRED"
        + reason). 3 new tests.
  - [x] **4.2.8 Report session-filter** *(2026-04-19)* — `_count_drawers`
        + `_hall_counts_for_palace` accept an optional `sessions` filter;
        match via the drawer frontmatter `source:` field; `format_pilot_report`
        filters both palaces by `plan.sessions` — apples-to-apples.
        1 new test.
  - [x] **4.2.9 Palace indexer + `mnemos mine --from-palace`** *(2026-04-19)* —
        `mnemos/palace_indexer.py`: walk_palace + parse_drawer + index_palace.
        Frontmatter-authoritative (wing/room/hall/source/importance/language),
        drop_and_reinit + index_drawers_bulk. CLI `--from-palace PATH`.
        `accept_skill(reindex=True)` default → `_reindex_after_accept` helper;
        no WARNING on success, advisory WARNING on failure. 13+2 new tests
        (palace_indexer + pilot reindex). Full suite 524 pass.
  - [~] **4.2.10 Latency realism + parallel-3** *(~1h, Finding 1)* —
        the spec assumed `25s/session`, reality is `~4 min/session`.
        Docs portion *(2026-04-19)*: spec §4.2.2 step 4 "Latency realism"
        line; CLI `Estimated time` based on the ~4 min/session × N formula.
        Parallel-3 implementation moved to the v0.4.2-alpha batch (below).

#### v0.4.2-alpha batch — full skill-mine prep + run *(next session)*

**Canonical plan:** [`docs/plans/2026-04-19-v0.4.2-full-skill-mine-prep.md`](plans/2026-04-19-v0.4.2-full-skill-mine-prep.md)

- [x] **4.2.11 Skill prompt multi-format** *(2026-04-19)* — the `mine-llm.md`
      canonical prompt + `skills/mnemos-mine-llm/SKILL.md` now support 4
      input format types: Type A (refined Sessions), Type B (curated
      Topics — drawer per H2 subsection, hall via content inference),
      Type C (Claude Code memory — one drawer per file,
      `type: user|feedback|project|reference` → hall mapping), Type D
      (MEMORY.md index → SKIP). CHUNKING section is type-aware (Type A
      section-based, Type B H2-based, Type C atomize). Source wikilink
      doesn't create a dead link for Type C (the v0.3.2 A5 synthetic-source
      rule was extended). The orchestrator (4.2.12) can now safely pass
      Sessions + Topics + memory files to this prompt.
- [x] **4.2.12 Orchestrator multi-source plan** *(2026-04-19)* — `build_plan`
      now discovers the Sessions/ + Topics/ + `cfg.mining_sources` union
      via the `_resolve_source_dirs(vault)` helper (rebuild.py pattern).
      `rglob("*.md")` is recursive — memory/ subfolders included.
      MEMORY.md + leading-underscore files are filtered. Dedup is via
      normpath. Plan API rename: `plan.sessions` → `plan.sources`,
      `session_count` → `source_count`, `sessions_needing_run` →
      `sources_needing_run`, `count_drawers_for_session` →
      `count_drawers_for_source`. CLI help text + Pilot plan output
      use the "Sources" label. 5 new tests (multi-source union,
      MEMORY.md skip, overlap dedup, `_` prefix skip, recursive subdir).
      Full suite **529 pass / 2 skip / 3 deselect**.
- [x] **4.2.13 CLI `--pilot-limit 0` no-limit mode** *(2026-04-19)* —
      `build_plan(limit=0)` now means "all sources" (full batch mine);
      negative limits still raise PilotError. CLI output is richer:
      `Sources: N files (X Sessions + Y Topics + Z ext) (limit=all|N)`
      breakdown + `_format_duration_estimate` helper (transitions from
      seconds to minutes to hours) + two estimates for sequential vs
      parallel-3 (target, 4.2.14). New `source_breakdown(vault,
      sources)` helper in pilot.py — preserves resolution order
      (Sessions, Topics, yaml mining_sources). 3 new tests (limit=0=all,
      negative limit reject, source_breakdown). Full suite 531 pass.
- [x] **4.2.14 Parallel execution + monitor-friendly progress** *(2026-04-19)* —
      `run_pilot(..., parallel=N, on_progress=cb)` now runs N-way concurrent
      `claude --print` via ThreadPoolExecutor. Outcomes are collected in
      plan order (completion order is non-deterministic). Thread-safe:
      `threading.Lock` for aggregation; ledger append relies on O_APPEND
      atomicity (the skill's subprocess-level write is <PIPE_BUF, append
      is atomic on POSIX + Windows NTFS). CLI `--parallel N` (default 1;
      3 recommended for full-mine) + `on_progress` callback prints in a
      Monitor-tool-friendly format: `[N/M] OK/SKIP/ERROR filename` after
      each file; every 10 files `Progress: N/M done · OK=X SKIP=Y ERROR=Z
      · elapsed · ETA`. ETA derived from elapsed/completed throughput —
      reflects parallel speedup automatically. 7 new tests (cap
      concurrency, preserve order, sequential=1 strict order, progress
      fires, resumed silent, reject parallel=0). **Follow-up patch**:
      the progress event dict now also carries `usage` (per-source
      TokenUsage) + `cumulative_tokens`; CLI shows `... → N drawers ·
      45k tok` per line + `... · 842k tok · ...` on the Progress line.
      `_fmt_tok` compact notation (k/M).
- [x] **4.2.15 Full skill-mine run** *(2026-04-19 → 20)* — parallel-3 mine
      completed on kasamd over 110 sources (69 Sessions + 15 Topics + 25
      memory + dedup tiebreak): 83.4 min wall clock, 57.3M tokens,
      98 OK / 3 SKIP / 9 ERROR, 571 drawers. ERRORs were categorized:
      5 Topics stubs + 2 `.gitkeep.md` legit-skips (SKIP ledger row added
      manually), 2 Type C memory real-failures retried → 2 OK/2 drawers.
      `.gitkeep*` discovery filter added (commit `6e8a3e3`). The
      `/mnemos-compare-palaces` skill ran a 5-axis comparison on 3 sample
      sessions — qualitative script vs skill evidence in the report:
      script 725 drawers (69% `facts` catch-all, Turkish section-header
      bleed, session-filename entity pollution); skill 572 drawers
      (balanced 5-hall, smart H1, clean entities, specific rooms). The
      user decided to **accept skill**: Mnemos/ → `_recycled/Mnemos-2026-04-20/`,
      Mnemos-pilot/ → Mnemos/, yaml `mine_mode: skill`, ChromaDB rebuilt
      from 572 drawers. Live `mnemos search` returns the skill's drawers.
      Recovery note: the first accept failed due to a Windows/OneDrive
      graph.json SQLite lock; succeeded after killing three zombie mnemos
      MCP servers (PID 25004/31896/43240) and force-removing the leftover
      Mnemos/.
- [x] **4.3.A Hook → skill-mine route + catch-up** — hook routes to `/mnemos-mine-llm` when `mine_mode: skill` (two-phase queue A+B, cap 10/fire), new `mnemos catch-up [--limit N] [--parallel N] [--dry-run]` command, `<vault>/Mnemos/_processing.xlsx` native-Excel audit trail (openpyxl + filelock). Spec `docs/specs/2026-04-22-4.3.A-hook-skill-mine-route-design.md`, plan `docs/plans/2026-04-22-v0.4-task-4.3.A-hook-skill-mine-route.md`. 10 tasks shipped across commits `8a8783a` … `b0f377e` on 2026-04-22 (561 tests pass, +19 new).
- [~] **4.3 Skill-recall** *(~5h, split into two ships)* — *(started 2026-04-23)*
  - [x] **4.3 first ship** *(2026-04-23, 18 tasks, commits `365da49`…`5943d2f`)* —
    cwd-aware auto-briefing + MCP recall_mode.
    Spec: [`docs/specs/2026-04-23-v0.4-task-4.3-first-ship-design.md`](specs/2026-04-23-v0.4-task-4.3-first-ship-design.md).
    Plan: [`docs/plans/2026-04-23-v0.4-task-4.3-first-ship.md`](plans/2026-04-23-v0.4-task-4.3-first-ship.md).
    - `mnemos/recall_briefing.py` (~780 lines) — path-checker SessionStart
      hook wrapper: CASE A first-visit fast path, SUB-B1 return-visit +
      staleness threshold (session_count diff ≥ 3 → sync regen), SUB-B2
      blocking catch-up (filelock + sync refine → mine → brief),
      statusline progress per phase, 37 tests.
    - `skills/mnemos-briefing/` — cwd-scope narrative synthesis skill
      (evolution-aware, with a "Revised/cancelled decisions" section
      for contradiction detection).
    - `mnemos/server.py` dynamic `build_instructions(cfg)` —
      `recall_mode: script` default / `skill` briefing-first.
    - `mnemos/config.py` — `recall_mode` yaml field.
    - `docs/prompts/refine-transcripts.md` — added `cwd:` field to
      frontmatter + CWD FIELD extraction instructions.
    - `scripts/backfill_cwd_frontmatter.py` — one-off migration; in
      kasamd, 40 sessions got a cwd (20 JSONLs archived).
    - `mnemos install-recall-hook` CLI (nested `matcher/_managed_by/hooks`
      schema, 600000ms timeout) + `init` integration with TR+EN i18n.
    - **Test delta:** +61 (9 backfill, 4 config, 5 mcp instructions,
      37 recall_briefing, 5 install-recall-hook, +1 statusline edge).
      Full suite **623 pass** / 2 skip / 3 deselect.
    - **Pending user smoke:** SUB-B2 blocking catch-up scenario (farcry-
      style cwd, sync refine+mine+brief in session 2 right after session 1
      is closed) — requires a manual Claude Code session. First-visit
      fast path offline smoke PASS (state.json record correct).
  - [x] **4.3.1 second ship** *(commit `7446976`, 2026-04-24)* —
    `/mnemos-recall <query>` explicit user skill shipped. In-session
    (no subprocess): `mnemos_search` → score threshold 0.015 (empirically
    calibrated from spec's 0.5 for k=60 RRF) → read top-5 drawers →
    narrative synthesis with `[[wikilink]]` citations. When drawer scores
    are weak, Step 7 Sessions grep rescue derives vault root, extracts
    2-4 keywords, Globs + Greps `<vault>/Sessions/`, reads top-3 matched
    Session files, synthesizes from their Özet / Alınan Kararlar
    sections with `[[session-slug]]` citations + attribution footer.
    Final soft fallback (Step 8) lists top 3 drawers only if both paths
    empty. Spec: [`docs/specs/2026-04-24-v0.4-task-4.3.1-explicit-recall-design.md`](specs/2026-04-24-v0.4-task-4.3.1-explicit-recall-design.md).
    Plan: [`docs/plans/2026-04-24-v0.4-task-4.3.1-explicit-recall.md`](plans/2026-04-24-v0.4-task-4.3.1-explicit-recall.md).
- [ ] **4.4 ~~Contradiction detection~~ → deferred to v0.5** (spec §2)
- [ ] **4.5 `mnemos settings` TUI** *(~2.5h)*
  - `mnemos/settings_tui.py` — numbered menu, 8 lines: backend, mine-mode,
    recall-mode, refine-hook, recall-hook, statusline, languages, briefing
    hint. Sub-actions delegate to existing commands (migrate, install-hook, etc.).
    i18n TR+EN.
- [ ] **4.6 Benchmark S+S combo** *(~3h)*
  - LongMemEval full 500q, measure only script-mine + script-recall
  - **Target: Recall@5 ≥ 93%** (marginal improvement on Phase 0's 90%;
    the original 95% claim dropped with the skill-first approach — no
    rerank in the S+S combo. Skill modes are qualitative, evaluated by
    pilot report.)
- [ ] **4.7 PyPI release v0.4.0**

---

## v0.4.1 — Polish batch ⏸ *(optional, after 4.7)*

Small UX and consistency fixes. Each is independent and not a ship blocker.
Derived from STATUS.md's "Optional v0.4.1 polish" section.

### Tasks

- [ ] **4.1.P1 Picker noise filter** *(~20 min)* —
  `_pick_unmined_sessions` + `_pick_unprocessed_jsonls` should silently
  drop `.gitkeep*` + `MEMORY.md` + leading-underscore files (share the
  same filter as `_discover_sources`). On kasamd, `.gitkeep.md` is still
  reaching the Phase A picker.
- [ ] **4.1.P2 Script miner section-header filename escape** *(~1h)* —
  even though script-mine isn't live, for benchmark and fallback scenarios
  strip the `alınan-kararlar/yapılanlar/özet/sonraki-adımlar/see-also/sorunlar`
  pattern from the slug.
- [ ] **4.1.P3 `mnemos mine --raw-only`** *(~30 min)* — 4.2.9
  follow-up; reindexes the raw collection without touching mined.
- [ ] **4.1.P4 Ledger/palace reconcile command** *(~1.5h)* —
  `mnemos processing-log repair` (or `mnemos mine --reconcile-ledger`).
  Walks the palace `wings/` frontmatter and backfills missing OK rows
  to the skill-mine ledger via the `count_drawers_for_source` pattern,
  updates `<vault>/Mnemos/_processing.xlsx`. 2026-04-22 kasamd finding:
  palace 593 drawers, ledger accounting 516 → 77 drawers accumulated as
  "ledger-skipped; filesystem-recovered". Pilot report
  `docs/pilots/2026-04-19-v0.4-phase1-real-vault-pilot.md` Finding 2.
  The same command with the `--rebuild` flag can also rebuild the xlsx
  from the two ledgers from scratch.
- [ ] **4.1.P5 Skill-mine-llm source field absolute-path discipline** *(~30 min)* —
  in the `skills/mnemos-mine-llm/SKILL.md` frontmatter schema section,
  emphasize that the `source:` field is **always an absolute path**.
  Add an instruction to the canonical prompt: "copy the input path
  verbatim into the frontmatter, don't make it cwd-relative." 2026-04-22
  audit: 3 drawers were written with relative paths
  (`source: memory/user_profile.md`). Test: even when the skill
  mini-pilot fixture passes a relative input, the frontmatter must be
  absolute.
- [ ] **4.1.P6 Hook refine-skill ledger-skip fallback** *(~45 min)* —
  at the end of `_run_skill_pipeline` Phase B, if `_latest_session_for_jsonl`
  returns None, fall back to the newest md file under Sessions/ (the
  logical equivalent of the `count_drawers_for_source` pattern in
  pilot.py). Planned in spec 4.3.A §8 but implementation took the short
  path and fell to ERROR.
- [ ] **4.1.P7 Legacy corrupt ledger rows cleanup** *(~15 min)* —
  refine ledger `processed.tsv` line 128 (`C:\Users<TAB>…`) +
  4 UUID-prefix-truncated lines (58/84/94/111) + legacy `palace=Mnemos-pilot`
  rows. Harmless, but closes a STATUS Pending user action.
- [ ] **4.1.P9 Phase A md ↔ xlsx jsonl-row sync** *(~30 min)* —
  found in the 2026-04-22 smoke: when a Session md is mined in Phase A,
  the xlsx row for the JSONL behind that md (which came from backfill)
  is not updated with the mine info → the same work shows up in two rows
  in xlsx (jsonl `mined_outcome=PENDING`, md `mined_outcome=OK`). Fix:
  in the Phase A loop, do a reverse lookup in the refine ledger for the
  session_md (which JSONL produced this session_md?); if found, write
  the same mine info to that jsonl row too. Alternative: instead of
  adding a new md row to xlsx, update the matched JSONL row in the
  refine ledger (single-source-of-truth per logical work unit).
- [ ] **4.1.P8 Wrapper → bg subprocess spawn reliability** *(~1h)* —
  in the 2026-04-22 real-vault test, when the user opened a new Claude
  Code session, the wrapper wrote the `.mnemos-active-sessions/<uuid>.json`
  marker but the `auto_refine_background` bg subprocess it spawned
  **died silently** — hook.log and hook-status.json were never updated.
  The same bg ran fine when invoked manually as
  `python -m mnemos.auto_refine_background ...` (started the Phase A mine).
  On Windows, the `DETACHED_PROCESS + CREATE_NEW_PROCESS_GROUP + stdout=DEVNULL`
  combo sometimes crashes Python child process handle inheritance —
  with stdout=DEVNULL, the import/startup error is completely invisible.
  Fix options: (a) redirect bg stdout to `<vault>/.mnemos-bg-last.log`
  (rotating, append), (b) after spawn, the wrapper waits 100ms + stats
  the bg process handle to check it's still alive, writes to the wrapper
  error log if not, (c) the bg subprocess writes "booted <ts>" as its
  first line to the log → the wrapper verifies the log 500ms later, retries
  if missing.

---

## v0.5.0 — Automation / Phase 2 ⏸

**Goal:** Mnemos stays healthy on its own — user intervention drops to a
minimum.

### Tasks

- [ ] **5.1 Write Phase 2 design spec** *(1h)*
  `docs/specs/YYYY-MM-DD-phase2-automation-design.md`
- [ ] **5.2 Session hooks** *(2-3h)*
  - Auto mine when a Claude Code session ends
  - `settings.json` hook: `SessionEnd → mnemos mine --incremental`
- [ ] **5.3 Contradiction detection / stale memory hygiene** *(2-3h, deferred from v0.4)*
  - Does a new memory contradict existing memories? (e.g. "we use X" vs
    a new "we switched to Y" → marks the old one outdated)
  - Skill-based: `/mnemos-hygiene` periodic audit — the skill compares
    new drawers against old ones, marks conflicts with a `contradicts:`
    frontmatter + `stale: true`. Instead of auto-recycle, moves to
    `_recycled/` with user consent.
- [ ] **5.4 Memory lifecycle / decay** *(2h)*
  - Old, never-searched, contradiction-marked memories fade out over time
  - `mnemos prune --dry-run` command
- [ ] **5.5 Knowledge graph deepening** *(3-4h)*
  - Cross-reference: indirect queries like "this memory is in project X,
    project X is in wing Y, wing Y made these decisions in the last Z days"
  - Extend the `mnemos_graph` tool
- [ ] **5.6 PyPI release v0.5.0**

---

## v0.6.0 — Community & Ecosystem ⏸

**Goal:** non-technical adoption drivers — language diversity, UI, marketing.

### Tasks

- [ ] **6.1 Extra language marker sets** *(1-2h each)*
  de, es, fr, ja — ~80 markers per language, in the existing EN/TR format
- [ ] **6.2 Obsidian plugin** *(~1-2 days)*
  TypeScript, in-vault UI — memory browser, timeline view, graph view
  (Obsidian canvas integration)
- [ ] **6.3 Demo video + launch blog post** *(~1 day)*
  YouTube 3-5 min demo + blog (Medium / Dev.to)
- [ ] **6.4 Contributor onboarding polish**
  Good-first-issue labels, issue templates, PR templates
- [ ] **6.5 PyPI release v0.6.0**

---

## Historical archive

Design/plan artifacts of delivered versions live under `docs/archive/`.
The active plan is this file; the archive is reference for design
rationale only. Index: [`docs/archive/README.md`](archive/README.md).

---

## Working style

1. Before starting a task, flip its checkbox in this file `[ ] → [~]` (in progress)
2. When the task is done, `[~] → [x]` + add commit hash (`*(commit <hash>, <date>)*`)
3. **Update [`STATUS.md`](../STATUS.md)** — add the new capability to the "What Mnemos can do today" section, update the "Where the roadmap ends up" line if needed. STATUS.md is the user-facing status file; no feature is added there without flipping the checkbox here, and no checkbox is flipped without adding the feature — the two get committed together
4. If scope changes, update the relevant line and add a new sub-task if needed
5. New phase design specs live under `docs/specs/`; in this ROADMAP only the summary
