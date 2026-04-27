# Mnemos — Project Status

**Last updated:** 2026-04-27 — v1.1.0 **shipped to GitHub** ([release tag](https://github.com/mnemos-dev/mnemos/releases/tag/v1.1.0)). G12 empirical validation **passed** (Test A graceful /exit, Test B briefing inject, Test C X-close sync fallback — all green on kasamd). Merge `ebee2f4` to main; 527 pass / 2 skip / 3 deselect. 🟡 **Pending user action:** G13.4 PyPI publish (`python -m twine upload dist/mnemos_dev-1.1.0*`) — deferred 24h for extra observation per staged-rollout preference.
**Stable PyPI version:** `v0.3.3` (v0.x atomic-paradigm — still default `pip install mnemos-dev` until v1.1.0 PyPI upload)
**Alpha:** `v1.0.0a1` — tag pushed to GitHub, never uploaded to PyPI (superseded by v1.1.0)
**Released:** `v1.1.0` — SessionEnd-driven memory architecture, GitHub release live, PyPI pending
**Canonical plan:** [`docs/ROADMAP.md`](docs/ROADMAP.md)
**v1.0 spec:** [`docs/specs/2026-04-25-v1.0-narrative-pivot-design.md`](docs/specs/2026-04-25-v1.0-narrative-pivot-design.md) · **v1.0 plan:** [`docs/plans/2026-04-25-v1.0-narrative-pivot.md`](docs/plans/2026-04-25-v1.0-narrative-pivot.md)
**v1.1 spec:** [`docs/specs/2026-04-26-v1.1.0-sessionend-driven-memory-design.md`](docs/specs/2026-04-26-v1.1.0-sessionend-driven-memory-design.md) · **v1.1 plan:** [`docs/plans/2026-04-26-v1.1.0-sessionend-driven-memory.md`](docs/plans/2026-04-26-v1.1.0-sessionend-driven-memory.md)

This file is the single-glance answer to: *why does Mnemos exist, what can it
do right now, and what will it do when the roadmap is complete?*

---

## 1. Why Mnemos exists

Hundreds of Claude Code sessions live in `~/.claude/projects/*.jsonl`. Decisions,
debugging notes, preferences, hard-won context — all locked in files nobody
re-opens. Every new session starts from zero. Your AI never *remembers you*.

**v0.x bet (MemPalace inspired):** atomic fragmentation — split conversations
into small "drawer" pieces and vector-index them. Measurement disproved this:
the RRF score band stuck at 0.014–0.017, synthesis fed better from narrative
than from fragments, and the 600-node graph went unused.

**v1.0 bet (narrative-first pivot, 2026-04-25):**
- **Sessions are the single memory unit.** Every conversation becomes one rich markdown note.
- **Wikilink graph.** `[[Project X]]` matches connect Sessions sparsely but meaningfully.
- **Identity Layer** (`<vault>/_identity/L0-identity.md`). A persistent user profile
  distilled from all Sessions. The briefing reads this as the base layer every session.
- **3-layer briefing skill.** Identity (3K) + cwd Sessions (8K) + 1-hop wikilink
  cross-context (4K), hard cap 15K.

The mining pipeline (~3K LOC + ~200 tests) was deleted. The
`legacy/atomic-paradigm` branch and `v0.4.0-archived` tag are preserved as a
fallback.

---

## 2. What Mnemos can do today (v1.0.0a1)

### Stable — `pip install mnemos-dev` still installs v0.3.3 (atomic paradigm)

The PyPI default is the v0.x stable. v1.0 alpha is **not yet published** to PyPI.
For early adopters: `pip install git+https://github.com/mnemos-dev/mnemos@v1.0.0a1`.

### v1.0 alpha capabilities (live in author's vault)

**Memory storage**
- Obsidian-native: every memory is a `.md` file you read/edit/delete
- `<vault>/Sessions/<date>-<slug>.md` — refined Claude Code transcripts (one per session)
- `<vault>/_identity/L0-identity.md` — persistent user profile (after `mnemos identity bootstrap`)
- `<vault>/_identity/_history/<date>-bootstrap.md` — bootstrap snapshots
- `<vault>/_identity/L0-identity.md.bak-*` — pre-refresh backups (rolling window 5)
- ChromaDB OR sqlite-vec backend for vector search; switch via `mnemos reindex --backend X`

**Refine prompt v2 (tag + wikilink hybrid)**
- Each Session frontmatter carries: `tags: [session-log, proj/<wing>, tool/<svc>, person/<name>, file/<repeating>, skill/<cmd>]`
- Each Session's `cwd:` field captured from JSONL first message
- Prose entities wikilink'd on first mention (`[[Mnemos]]`, `[[Tugra]]`, `[[Supabase]]`)
- Quality control checklist: ≥1 `proj/*` tag + ≥1 prose wikilink + tag-prose consistency

**Identity Layer (Task 10–14)**
- `mnemos identity bootstrap` — read all Sessions (≤150K token cap with hybrid sampling), produce structured profile
- `mnemos identity refresh` — incremental update (gates: ≥10 new sessions + identity-relevant tags); pre-refresh backup
- `mnemos identity rollback [target]` — restore from `.bak-*` snapshot
- `mnemos identity show` — print current profile
- Scope-aware preferences: `(general)` vs `(proj/<name>)` to prevent identity contamination
- `mnemos_status` MCP tool reports `identity_last_refreshed` + `identity_session_count_at_refresh`

**3-layer briefing skill v2**
- Identity Layer (3K cap, fixed) → Cwd Layer (8K priority-1) → Cross-context (4K priority-2)
- Hard cap 15K input, output 200–400 word narrative
- Identity-less graceful: skips Identity section, cwd briefing still works
- Empty cwd: emits "No prior sessions recorded for this cwd yet" message

**MCP tool surface (6 tools, down from 8)**
- `mnemos_search` (collection="raw" only, "mined"/"both" deprecated → warn + raw fallback)
- `mnemos_recall` (level="L0" only, L1/L2 returns deprecated marker)
- `mnemos_wake_up` (returns Identity Layer content)
- `mnemos_graph(entity)` — Obsidian wikilink graph scan (was SQLite triple store)
- `mnemos_timeline(entity)` — chronological wikilink mention list
- `mnemos_status` — vault stats + identity metadata

**Hooks**
- `mnemos install-hook --v1` — atomic idempotent settings.json install (auto-refine + recall-briefing)
- Stale hook graceful failure shim — old v0.x entries print "Run install-hook --v1" + exit 0
- Statusline format updated (drops mining fields, adds `identity_last_refreshed`)

**CLI**
- `mnemos init` v2 — drops mine_mode prompt, adds identity bootstrap phase 6 (TR+EN i18n)
- `mnemos identity {bootstrap,refresh,rollback,show}`
- `mnemos reindex --backend X` (replaces `mnemos migrate`)
- `mnemos install-hook --v1` (replaces v0.x install-hook + install-recall-hook)
- Removed (with friendly migration nudge): `mnemos {mine, catch-up, migrate, processing-log, pilot}`, `mnemos import {chatgpt, slack, markdown, memory, claude-code}`

**Test suite**
- 452 pass / 2 skip / 3 deselect / 1 known EOL artifact (`test_mnemos_recall_skill_junction_zero_drift` — CRLF vs LF junction drift, mechanical)
- v0.x mining-bound tests deleted (~200 tests)
- v1.0 added: `test_identity.py` (18 tests), `test_mcp_v1.py` (8 tests), `test_briefing_v2.py` (5 tests), `test_install_hook_v1.py` (4 tests), `test_reindex.py` (3 tests), `test_cli_identity.py` (2 tests), `test_cli_reindex.py` (1 test), etc.

### v1.0.0a1 release artifacts (built, NOT published to PyPI)

- `dist/mnemos_dev-1.0.0a1-py3-none-any.whl` (100,461 bytes, on disk in v1.0 worktree)
- `dist/mnemos_dev-1.0.0a1.tar.gz` (586,634 bytes)
- Tag `v1.0.0a1` pushed to GitHub
- Branch `feature/v1.0-pivot` pushed to GitHub
- Main updated with all 33+2 commits, pushed to GitHub

### Pre-v1.0 stable releases (preserved on PyPI)

- v0.1.0 — First Breath (core MCP, regex mining, ChromaDB)
- v0.2.0 — Full Memory / Phase 0 (L0–L3 stack, dual collection RRF, multilingual)
- v0.3.0 — First-Run Experience (`mnemos init`, refine skill, `.mnemos-pending.json`)
- v0.3.1 — Backend UX (`mnemos migrate`, `mnemos init` backend prompt, error wrapping)
- v0.3.2 — Palace Hygiene (atomic rebuild, TR-aware wing canonicalization)
- v0.3.3 — Post-v0.3.2 cleanup (migrate rollback+lock, score parity, slow-tests)

---

## 3. v1.0 alpha rollout — current state (2026-04-26)

### Completed

- ✅ All 31 v1.0 pivot tasks (Tasks 0–30) — see `docs/plans/2026-04-25-v1.0-narrative-pivot.md`
- ✅ Local merge `feature/v1.0-pivot` → `main` (fast-forward, 33 commits)
- ✅ Push origin main + feature branch + tag v1.0.0a1
- ✅ Build artifacts in `dist/`
- ✅ Switched author's editable install to v1.0 (via merge, automatically)
- ✅ Ran `mnemos install-hook --v1` against kasamd
- ✅ Two post-tag hotfixes shipped to main:
  - `d579362` — install-hook commands needed `--vault` flag (not positional)
  - `04e6d03` — refine ledger reads needed `errors='replace'` for non-UTF-8 bytes
- ✅ kasamd cwd-coverage backfill: 22 Sessions backfilled (ProcureTrack 8, Mnemos 5, valves 1, TPAO 2, Safa Clutch 1, GYP+Satin-Alma 5). **86% coverage (68/79)**.
- ✅ kasamd backup zip taken: `kasamd-pre-v1-2026-04-26.zip` (17 MB) on Masaüstü
- ✅ farcry cwd test PASS — briefing inject works, real history surfaced ("Far Cry 7 → Shimeji tavuk pivot")
- ✅ procuretrack cwd test (1st visit, CASE A — silent expected) confirmed

### 🟡 Pending user actions

1. **Identity bootstrap** (~5–10 min LLM call, subscription quota): `mnemos identity bootstrap --vault "C:/Users/tugrademirors/OneDrive/Masaüstü/kasamd"`. Generates `_identity/L0-identity.md` from 79 Sessions.
2. **More real-world testing**: open new Claude Code sessions in various cwds:
   - Re-test `C:\Projeler\Satın Alma\procuretrack` (now 2nd visit, SUB-B1 should brief)
   - Test `C:\Projeler\mnemos` (rich Sessions, briefing should pivot summary)
   - Test `C:\Users\tugrademirors\OneDrive\Masaüstü\Claude Çalışma Dosyası` (5 backfilled Sessions)
3. **PyPI alpha publish** (deferred until validated; v1.1 likely supersedes v1.0.0a1 publish): `python -m twine upload C:/Projeler/mnemos-v1.1/dist/mnemos_dev-1.0.0a1*` (rebuild from current worktree)
4. **GitHub pre-release create**: `gh release create v1.0.0a1 --prerelease --title "v1.0.0a1 — Narrative-First Pivot Alpha" --notes-file CHANGELOG.md dist/mnemos_dev-1.0.0a1*`

### Known caveats

- 11 Sessions still cwd-less (1 LightRAG + 9 General/setup + 1 no-frontmatter) — acceptable; setup work, not project-specific. Can be tag/project-fallback'd later if needed.
- 1 EOL test failure (`test_mnemos_recall_skill_junction_zero_drift`) — mechanical CRLF/LF mismatch. Will resolve naturally next time the SKILL.md is regenerated.

---

## 4. Next session starts here (post-`/clear`, 2026-04-26)

**v1.1.0 implementation COMPLETE (G1-G11 + G13.1-G13.3). Validation + publish pending.**

### v1.1 implementation summary (2026-04-26)

| Group | Tasks | Status | Highlights |
|---|---|---|---|
| G1 Config schema | 5 | done | `schema_version`, `RefineConfig`, `BriefingConfig`, `IdentityConfig`, atomic `save_config` |
| G2 Refine pipeline | 6 | done | `pick_jsonls(cfg, ...)`, `find_unrefined_jsonls_for_cwd(cfg)`, hook caller cfg-thread |
| G3 Identity gate | 5 | done | `mnemos/readiness.py`, bootstrap eligibility gate + `--force`, `refresh` reads `cfg.identity.*` |
| G4 Identity-refresh skill | 3 | done | `skills/mnemos-identity-refresh/{SKILL.md, prompt.md}` + junction zero-drift test |
| G5 Briefing v3 | 3 | done | smart-layered + revision-aware prompt rewrite, junction re-pointed to v1.1 worktree |
| G6 SessionStart updates | 5 | done | readiness gate, `systemMessage`, cross-check directive, sync fallback, vault-aware first-visit |
| G7 SessionEnd hook + worker | 6 | done | `mnemos/session_end_hook.py` with breakaway flag + 3-stage pipeline + stale-hook detection |
| G8 install-end-hook CLI | 4 | done | atomic install/uninstall, idempotent, surgical |
| G9 Settings TUI | 7 | done | `mnemos/settings_tui.py` + `mnemos settings` command, real progress display, TR/EN i18n |
| G10 Init flow | 3 | done | refine quota dialog + `install-end-hook` prompt + 11 i18n keys |
| G11 Documentation | 5 | done | README hero, CHANGELOG v1.1.0 entry, identity-bootstrap classification, CONTRIBUTING no-API rule, CI grep |
| G12 Empirical validation | 3 | 🟡 deferred | needs real Claude Code sessions in farcry / procuretrack / mid-stream X-close |
| G13.1-13.3 Release prep | 3 | done | version bump 1.0.0a1 → 1.1.0, wheel + sdist built, clean-venv smoke OK |
| G13.4 Publish | 1 | 🟡 deferred | PyPI + GitHub release pending user explicit go-ahead |

**Build artifacts on disk (gitignored):**
- `dist/mnemos_dev-1.1.0-py3-none-any.whl` (117 KB, +17 KB vs v1.0.0a1)
- `dist/mnemos_dev-1.1.0.tar.gz` (657 KB, +70 KB vs v1.0.0a1)

🟡 **Pending user actions before release:**

1. **G12 empirical validation** — open real Claude Code sessions in:
   - `C:\Users\tugrademirors\OneDrive\Masaüstü\farcry` — full /exit lifecycle smoke (SessionEnd fires → worker refines + briefs → next session opens with fresh cache)
   - `C:\Projeler\Satın Alma\procuretrack` — repeat
   - mid-stream X-close — confirm SessionStart sync fallback catches the missed SessionEnd next session
   - Watch the SessionEnd worker test infra at `~/.claude/test-session-end/` (`mnemos-end-smoke-test` entry) for breakaway survival.

2. **G13.4 PyPI publish + GitHub release** (only after G12 passes):
   ```bash
   python -m twine upload C:/Projeler/mnemos-v1.1/dist/mnemos_dev-1.1.0*
   gh release create v1.1.0 \
     --title "v1.1.0 — SessionEnd-Driven Memory" \
     --notes-file CHANGELOG.md \
     C:/Projeler/mnemos-v1.1/dist/mnemos_dev-1.1.0-py3-none-any.whl \
     C:/Projeler/mnemos-v1.1/dist/mnemos_dev-1.1.0.tar.gz
   git tag v1.1.0 -a -m "v1.1.0 — SessionEnd-Driven Memory"
   git push origin v1.1.0
   ```

3. **kasamd identity bootstrap** (still pending from v1.0):
   `mnemos identity bootstrap --vault "C:/Users/tugrademirors/OneDrive/Masaüstü/kasamd"` — once available, the bootstrap eligibility gate (25%) will assess kasamd readiness; pass `--force` to bypass.

4. **Test infra cleanup** — `~/.claude/test-session-end/` and the `mnemos-end-smoke-test` SessionEnd entry in `settings.json` were left active during the design phase. After G12 passes, delete the dir + remove the entry (or just run `mnemos install-end-hook --uninstall` and let the canonical install replace it).

### Original v1.1 design conversation (still applies)

**v1.1.0 design + implementation plan COMPLETE. Implementation NOT started.** [Original next-session block — preserved for archaeology]

**🌳 Worktree migration completed (2026-04-26):**
- `feature/v1.0-pivot` → merged to `main` via `fe1837f` (resolves STATUS+ROADMAP conflicts; main now reflects v1.0.0a1 alpha + bg-catchup hotfix + v1.1 design+plan)
- New `feature/v1.1.0` branch + worktree at **`C:/Projeler/mnemos-v1.1`** (this directory)
- Editable install reinstalled: `mnemos` package now resolves to `C:/Projeler/mnemos-v1.1/mnemos/__init__.py`
- Old `C:/Projeler/mnemos-v1.0` worktree (feature/v1.0-pivot branch) STILL EXISTS as backup; can be removed later via `git worktree remove C:/Projeler/mnemos-v1.0`
- Implementation paths in this STATUS + spec + plan reference `C:/Projeler/mnemos-v1.1`

At the end of that day's session:
1. v1.0 bug fix shipped — `recall_briefing.py` re-entry guard moved to AFTER
   `--catchup` parsing (`a19cfb9`). `HOOK_ACTIVE_ENV=1` no longer blocks the
   bg subprocess. +2 regression tests, 455 pass full suite. Empirical
   validation: produced a 4128 B briefing cache for kasamd procuretrack —
   no cache was being written at all before the fix.

2. v1.1 design conversation complete (5 issues brainstormed, all resolved):
   - Issue 1: Refine pipeline configurability + Settings TUI
   - Issue 2: Identity bootstrap eligibility gate + auto-refresh from SessionEnd
   - Issue 3: Briefing readiness gate (default 60%)
   - Issue 4: Briefing prompt v3 (smart-layered + revision-aware)
   - Issue 5: In-session briefing UX (systemMessage + cross-check directive)
   - Foundation: SessionEnd-driven worker pipeline (refine + brief + identity check)
     with CREATE_BREAKAWAY_FROM_JOB for X-close survival

3. Spec written + committed (`10fa3ca`):
   `docs/specs/2026-04-26-v1.1.0-sessionend-driven-memory-design.md` — 818
   lines, 15 sections. Hard invariant: NO Anthropic API calls anywhere
   (subscription only via `claude --print` skill subprocess, `_child_env`
   strips the API key).

4. Implementation plan written + committed (`2e428e3`):
   `docs/plans/2026-04-26-v1.1.0-sessionend-driven-memory.md` — 4748 lines,
   13 task groups, 55 TDD tasks, ~275 steps. Every task uses the TDD pattern
   (failing test → minimal impl → green → commit).

5. Empirical SessionEnd smoke (2026-04-26 cycle on kasamd farcry):
   - /exit graceful close: SessionEnd fires, worker `with_breakaway` survives ✓
   - X-close idle: SessionEnd fires, worker survives 30s via BREAKAWAY ✓
   - X-close mid-stream: SessionEnd misses → SessionStart sync fallback catches it
   - Test infra: `~/.claude/test-session-end/` (hook + worker + inspect script)
     and the `mnemos-end-smoke-test` SessionEnd entry in settings.json are
     CURRENTLY ACTIVE.

**Next session start:**

Run the plan with `superpowers:subagent-driven-development` or
`superpowers:executing-plans`. Recommendation: subagent-driven (fresh subagent
per task, two-stage review, parallel-friendly). First task: **G1 Task 1.1 —
Add schema_version field with backward-compat read** (`mnemos/config.py` +
`tests/test_config_v1_1.py`, TDD pattern, ~5 steps, ~15 minutes).

Group order: G1 (config foundation) → G2 (refine config) → G3 (identity gate)
→ G4 (refresh skill) → G5 (briefing v3) → G6 (SessionStart updates) → G7
(SessionEnd worker) → G8 (install-end-hook CLI) → G9 (Settings TUI) → G10
(init flow) → G11 (docs) → G12 (empirical validation, BLOCKING) → G13 (release).

🟡 **Pending user actions (defer):**
- Test infra cleanup: `~/.claude/test-session-end/` dir + the
  `mnemos-end-smoke-test` SessionEnd entry in settings.json. Can stay as
  reference for G7 during implementation, then clean up.
- Identity bootstrap (pending since v1.0): `mnemos identity bootstrap
  --vault "C:/Users/tugrademirors/OneDrive/Masaüstü/kasamd"` — will hit
  the threshold gate alongside v1.1 G3 (~10% have, 25% needed); bypassable
  with `--force`. Run with --force during implementation if needed.
- PyPI publish v1.0.0a1 (deferred): `python -m twine upload dist/...` — once
  v1.1 is ready, publish v1.1.0 directly; the v1.0.0a1 alpha tag stays on
  GitHub.


1. Read `STATUS.md` (this file) — see §3 "v1.0 alpha rollout" for current state
2. Read `docs/ROADMAP.md` — version table shows v1.0.0a1 alpha, v1.0.0 stable next
3. Run `git log --oneline -10` — see latest commits (HEAD = `04e6d03` ledger UTF-8 fix)
4. Give <100 word summary, ask "Devam mı, başka iş mi?"

**Most likely next work:**
1. **`mnemos identity bootstrap`** — single LLM call, ~5–10 min. Creates user profile.
2. After identity is in place, retest cwd-aware briefing — it should now have a "Kullanıcı profili" section in addition to Aktif durum/Geçerli kararlar/etc.
3. Continue alpha validation in real cwds for 1–2 weeks. Fix any rough edges.
4. Once stable: `python -m twine upload dist/...` (PyPI alpha publish) + `gh release create` (GitHub pre-release).

**If issues surface:** kasamd backup is at `C:/Users/tugrademirors/OneDrive/Masaüstü/kasamd-pre-v1-2026-04-26.zip` (17 MB, full vault snapshot). Recovery: unzip OR `git checkout legacy/atomic-paradigm` for code rollback.

---

## 5. Where the roadmap ends up (post-v1.0)

**v1.1 — Wikilink resolution intelligence.** Heuristics to merge `[[GYP]]` and
`[[GYP Energy]]` into a canonical entity, with manual override. Tag/project
fallback in briefing skill for cwd-less Sessions.

**v1.2 — Cross-vault recall.** Query memory across multiple Obsidian vaults
(work + personal) with vault-aware filtering.

**v1.3 — Obsidian plugin.** Native sidebar: memory browser, timeline view,
briefing inbox.

**v2.0 — Self-maintaining memory.** Stale-decision flagging, decay,
contradiction detection — the v0.5 Phase 2 ideas, rebased onto Sessions graph.

### The end state

> *A Claude Code user runs `pip install mnemos-dev && mnemos init && mnemos
> identity bootstrap`. Every past session becomes a Session note in their
> Obsidian vault, classified by project, linked by entity wikilinks. From that
> day forward, every Claude Code session opens with: a 3-section briefing
> (their identity profile + cwd-specific decisions + cross-context wikilink
> neighbors). Their AI knows them. Their memory is human-readable. Nothing is
> locked in a proprietary binary.*

---

## Check-in rhythm

This file is updated at every meaningful state transition. v1.0 alpha
validation is the current cycle; expect §3 to evolve as testing surfaces
edge cases and §4 to update when each pending action is taken.
