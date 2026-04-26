# Mnemos — Project Status

**Last updated:** 2026-04-26 — **v1.0.0a1 alpha shipped (git only, NOT yet on PyPI)** · narrative-first pivot complete · 33 commits + 2 post-tag hotfixes · kasamd v1.0 hooks live, briefing inject working
**Stable PyPI version:** `v0.3.3` (the v0.x atomic-paradigm — still default for `pip install mnemos-dev`)
**Alpha:** `v1.0.0a1` — tag pushed to GitHub, **not** yet uploaded to PyPI (pending real-world validation)
**Canonical plan:** [`docs/ROADMAP.md`](docs/ROADMAP.md) · **v1.0 spec:** [`docs/specs/2026-04-25-v1.0-narrative-pivot-design.md`](docs/specs/2026-04-25-v1.0-narrative-pivot-design.md) · **v1.0 plan:** [`docs/plans/2026-04-25-v1.0-narrative-pivot.md`](docs/plans/2026-04-25-v1.0-narrative-pivot.md)

This file is the single-glance answer to: *why does Mnemos exist, what can it
do right now, and what will it do when the roadmap is complete?*

---

## 1. Why Mnemos exists

Hundreds of Claude Code sessions live in `~/.claude/projects/*.jsonl`. Decisions,
debugging notes, preferences, hard-won context — all locked in files nobody
re-opens. Every new session starts from zero. Your AI never *remembers you*.

**v0.x bahis (MemPalace inspired):** atomic fragmentation — sohbetleri küçük
"drawer" parçalarına bölüp vector index'le. Ölçüm çürüttü: RRF skor bandı
0.014–0.017'de takıldı, sentez narrative'den iyi besleniyor, 600-node graph
kullanılmıyor.

**v1.0 bahis (narrative-first pivot, 2026-04-25):**
- **Sessions tek memory unit.** Her sohbet bir zengin markdown notu.
- **Wikilink graph.** `[[Project X]]` eşleşmeleri Sessions'ları seyrek-anlamlı bağlar.
- **Identity Layer** (`<vault>/_identity/L0-identity.md`). Tüm Sessions'tan damıtılan
  kalıcı user profile. Briefing her oturumda bunu base layer olarak okur.
- **3-katman briefing skill.** Identity (3K) + cwd Sessions (8K) + 1-hop wikilink
  cross-context (4K), hard cap 15K.

Mining pipeline (~3K LOC + ~200 test) silindi. Geri dönüş için
`legacy/atomic-paradigm` branch + `v0.4.0-archived` tag korunuyor.

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
- Quality control checklist: ≥1 `proj/*` tag + ≥1 prose wikilink + tag-prose tutarlılığı

**Identity Layer (Task 10–14)**
- `mnemos identity bootstrap` — read all Sessions (≤150K token cap with hybrid sampling), produce structured profile
- `mnemos identity refresh` — incremental update (gates: ≥10 new sessions + identity-relevant tags); pre-refresh backup
- `mnemos identity rollback [target]` — restore from `.bak-*` snapshot
- `mnemos identity show` — print current profile
- Scope-aware preferences: `(general)` vs `(proj/<name>)` to prevent identity contamination
- `mnemos_status` MCP tool reports `identity_last_refreshed` + `identity_session_count_at_refresh`

**3-layer briefing skill v2**
- Identity Layer (3K cap, sabit) → Cwd Layer (8K priority-1) → Cross-context (4K priority-2)
- Hard cap 15K input, output 200–400 word narrative
- Identity-less graceful: skips Identity section, cwd briefing still works
- Boş cwd: "No prior sessions recorded for this cwd yet" mesajı

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

1. **Identity bootstrap** (~5–10 dk LLM call, abonelik kotası): `mnemos identity bootstrap --vault "C:/Users/tugrademirors/OneDrive/Masaüstü/kasamd"`. Generates `_identity/L0-identity.md` from 79 Sessions.
2. **More real-world testing**: open new Claude Code sessions in various cwds:
   - Re-test `C:\Projeler\Satın Alma\procuretrack` (now 2nd visit, SUB-B1 should brief)
   - Test `C:\Projeler\mnemos` (rich Sessions, briefing should pivot summary)
   - Test `C:\Users\tugrademirors\OneDrive\Masaüstü\Claude Çalışma Dosyası` (5 backfilled Sessions)
3. **PyPI alpha publish** (deferred until validated): `python -m twine upload C:/Projeler/mnemos-v1.0/dist/mnemos_dev-1.0.0a1*`
4. **GitHub pre-release create**: `gh release create v1.0.0a1 --prerelease --title "v1.0.0a1 — Narrative-First Pivot Alpha" --notes-file CHANGELOG.md dist/mnemos_dev-1.0.0a1*`

### Known caveats

- 11 Sessions still cwd-less (1 LightRAG + 9 General/setup + 1 no-frontmatter) — acceptable; setup work, not project-specific. Can be tag/project-fallback'd later if needed.
- 1 EOL test failure (`test_mnemos_recall_skill_junction_zero_drift`) — mechanical CRLF/LF mismatch. Will resolve naturally next time the SKILL.md is regenerated.

---

## 4. Next session starts here (post-`/clear`)

**Trigger:** type `mnemos` or `devam`. Resume protocol kicks in (CLAUDE.md):

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
