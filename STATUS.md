# Mnemos — Project Status

**Last updated:** 2026-04-22 (4.3.A shipped: hook artık `/mnemos-mine-llm` çağırıyor, `mnemos catch-up` komutu, `_processing.xlsx` audit; 561 test pass +19 new; sonraki: 4.3 skill-recall)
**Stable PyPI version:** `v0.3.3` · **Next:** `v0.4.0` (AI Boost / Phase 1 — 4.3 + 4.5 + 4.6 + 4.7 remaining)
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

### Released — v0.3.1 Backend UX (2026-04-17, GitHub)

- ✅ **2026-04-17 parity benchmark** — sqlite-vec ve ChromaDB LongMemEval
  10q subset'inde dördüncü ondalığa kadar aynı: R@5=0.90, R@10=0.90,
  NDCG@10=0.7393, 8027 drawer, ~62 dk. Backend seçimi recall-nötr.
- ✅ **`mnemos init` backend prompt** — `use_llm` sonrası, yaml yazımından
  önce. [C]hromaDB (default) / [S]qlite-vec, TR+EN i18n, Windows+Py3.14
  platform hint. Re-run idempotent (yaml'da `search_backend` varsa sormaz).
- ✅ **`mnemos migrate --backend X`** — pre-flight plan (drawer + source
  file sayısı + süre tahmini ±%30), `--dry-run`, dated backups (aynı gün
  ikinci migrate `.bak-DATE.2` suffix), yaml update, mine_log clear, rebuild,
  `--no-rebuild` opt-out, drawer-drop uyarısı (>%20 düşüş → "backup preserved").
- ✅ **`BackendInitError` wrapper** — ChromaDB HNSW / sqlite-vec DatabaseError
  gibi init hataları tek satır "use `mnemos migrate --backend <other>`"
  önerisiyle surface oluyor. Traceback `--verbose` için saklı.
- ✅ **`mnemos status` backend satırı** — `Backend: <name> (<path> · N drawers · X MB)`.
  `SearchBackend.storage_path()` abstract + `get_stats()["storage_bytes"]`.
- ✅ **README Troubleshooting + hero tweak** — "Two vector backends" vurgusu,
  index corruption → migrate sqlite-vec recipe. CONTRIBUTING "backend count
  stays at two" architectural line (Qdrant/LanceDB gibi 3. backend PR'ı için
  yüksek bar).
- ✅ **Miner regression hotfix** — `_dedup_by_id` bulk indexer'da duplicate
  drawer ID'yi tolere ediyor (v0.2 bulk API sonrası çıkan crash).
- ✅ **Clean-vault pilot** (`docs/pilots/2026-04-17-v0.3.1-backend-pilot.md`):
  init → sqlite-vec → mine → dry-run migrate → real migrate → migrate back
  → search → same-backend noop hepsi yeşil. Tag `v0.3.1` + GitHub release at
  <https://github.com/mnemos-dev/mnemos/releases/tag/v0.3.1> + PyPI
  <https://pypi.org/project/mnemos-dev/0.3.1/> (wheel + sdist asset'li).

### Released — v0.3.2 Palace Hygiene (2026-04-18)

- ✅ **Six pipeline hygiene fixes (Group A)** — TR-aware wing canonicalization
  (`94b624d`); lazy hall/`_wing.md`/`_room.md` creation so empty wings and
  phantom rooms don't pollute the graph view (`590f302`); `tags[0]` no longer
  promoted to room (`0e72389`); drawer filenames use source date with
  word-boundary slug so `YYYY-MM-DD-YYYY-MM-DD-…` double prefix is gone
  (`6707010`); drawer body gains `# <smart-title>` H1 + `> Source: [[…]]`
  wikilink, synthetic/manual sources skip the wikilink to avoid dead
  `[[unknown]]` links (`13fc74c` + review fix `9532caf`); entity hygiene —
  no tags as entities, case-preserve dedup (`bbfa1b8`).
- ✅ **Atomic `mnemos mine --rebuild` (Group B)** — `mnemos/rebuild.py`
  orchestrator: resolve sources → pre-flight plan → dry-run gate → confirm
  → `.rebuild.lock.flock` → backup wings/index/graph → `drop_and_reinit()`
  + `KnowledgeGraph.reset()` → re-mine → verify → rollback on failure.
  `--dry-run` / `--yes` / `--no-backup` flags; `path` argument optional
  (falls back to `cfg.mining_sources` or auto-discovers `Sessions/` +
  `Topics/`). `SearchBackend.drop_and_reinit()` on both backends, `Palace
  .backup_wings()` with `.N` collision suffix, `KnowledgeGraph.reset()`
  (commits `2059783` / `6a9570d` / `1c4da1f` / `729eea4` / `b70a935` /
  `86a915b` / `85e301c`).
- ✅ **Auto-refine hook respects rebuild lock** — `mnemos/auto_refine_hook.py`
  silently exits if the rebuild orchestrator holds `.rebuild.lock.flock`;
  uses a 50 ms non-blocking probe so stale lock files (crashed prior
  rebuild) don't wedge the hook (`7f30777`).
- ✅ **Review fixes (post-Group-B)** — backend + graph handles now close in
  `finally` so the rollback path's `shutil.rmtree` won't hit Windows
  `WinError 32`; `_resolve_sources` called once through `plan
  ["sources_resolved"]` (no TOCTOU window between plan display and
  confirmation); `test_rebuild_happy_path` now parametrized across both
  backends (first end-to-end ChromaDB exercise of `rebuild_vault` — dir
  backup vs sqlite-vec's file backup); new `test_rebuild_succeeds_past_
  stale_lock_file` covers filelock's OS-level advisory semantics. 17
  tests in `test_rebuild.py`, all green (`d290de8`).
- ✅ **Test-suite repairs** — five pre-existing tests in `test_server.py`
  / `test_stack.py` assumed A2's old eager `_wing.md` behavior; seeded
  a minimal drawer per wing/room to trigger the lazy summary write. No
  production code changes (`509582f`).
- ✅ **Distribution-ready memory-source handling** — three post-pilot fixes
  so every Claude Code user (not just the author) gets rebuild-safe
  memory imports:
  - `MEMORY.md` index files + leading-underscore `.md` files are skipped
    by the miner (duplicate-signal noise) — `998a529`.
  - `mnemos import markdown|memory <path>` now appends the source to
    `mnemos.yaml`'s `mining_sources` (idempotent, yaml-preserving,
    Windows-normalized) so rebuilds pick it up automatically — `e9f3d6d`.
  - `_resolve_sources` is now additive: always auto-discovers the
    vault's internal `Sessions/` + `Topics/` and UNIONs with configured
    `mining_sources` entries (dedup by `os.path.normpath`). Caught by
    the round-trip rebuild pilot, which initially dropped from 683 to
    100 drawers because `mining_sources` was replacing auto-discover —
    `bb53892`.
- ✅ **Real-vault pilot complete** — kasamd rebuild + 5 external memory
  folder re-import + round-trip validation. Final: 683 drawers (up
  from 670 pre-v0.3.2 despite skipping MEMORY.md indexes), 16 wings,
  session-log entity pollution 0 (was 457), phantom hall dirs 0 (was
  138), double-date filenames 4 (was 69). Source file sha256 hashes
  unchanged — rebuild never modifies Sessions/Topics.
- ✅ **PyPI release v0.3.2** — wheel + sdist published to
  <https://pypi.org/project/mnemos-dev/0.3.2/>, GitHub release at
  <https://github.com/mnemos-dev/mnemos/releases/tag/v0.3.2>
  (wheel + sdist asset'li). Tag `v0.3.2` pushed.

### Released — v0.3.3 Post-v0.3.2 cleanup (2026-04-19)

- ✅ **Migrate rollback + lock** — `MigrateError` raised on rebuild
  failure (old backend storage + mine_log + yaml restored atomically,
  partial new-backend storage wiped). `.migrate.lock.flock` advisory
  lock prevents concurrent migrates on the same vault. Lock is
  OS-held so crashed processes don't leave stale lock files.
- ✅ **Dry-run estimate readable on tiny vaults** — `~0–0 minutes` →
  `~2–3 seconds` via `MigrationPlan.format_estimate()`, with seconds
  floor at 1 so single-drawer vaults still show a real number.
- ✅ **sqlite-vec score parity with ChromaDB** — `_l2_to_score` uses
  linear `1 - L2/2` (was cosine `1 - L2²/2`). Ranking unchanged
  (monotonic in L2, benchmark recall identical) but surface scores
  now sit in the 0.3–0.7 band instead of the confusing 0.01–0.02
  range users saw on sqlite-vec.
- ✅ **Test suite green in ~5 min** — `@pytest.mark.slow` marker
  registered in pyproject, durability tests tagged + subprocess
  timeout bumped to 600 s, default `addopts = "-m 'not slow'"`.
  Full default run: **463 passed, 2 skipped, 3 deselected**.
- ✅ **PyPI release v0.3.3** — wheel + sdist published to
  <https://pypi.org/project/mnemos-dev/0.3.3/>, GitHub release at
  <https://github.com/mnemos-dev/mnemos/releases/tag/v0.3.3>.

### Post-v0.3.3 repo polish (2026-04-19, not a release — docs/meta only)

- ✅ **GitHub community surface** (`.github/`) — structured bug + feature
  issue forms (dropdowns for backend / OS / Python version), PR
  template with checklist (pytest / CHANGELOG / ROADMAP checkbox / no
  secrets), `config.yml` redirects blank-issue traffic to ROADMAP /
  CHANGELOG / Discussions.
- ✅ **CI** — `.github/workflows/test.yml` runs the default pytest
  suite on push + PR, matrix ubuntu + windows × Python 3.10 + 3.12.
  README hero bar now carries a live "tests" badge and a live PyPI
  version badge (replaced the static v0.3.x one).
- ✅ **Policy documents** — `SECURITY.md` (latest-minor support
  policy + private GitHub advisory reporting) and `CODE_OF_CONDUCT.md`
  (Contributor Covenant v2.1). Both appear in the GitHub sidebar
  automatically.
- ✅ **Visual identity** — `assets/make_social_preview.py` generates
  a 1280×640 PNG (deep-indigo gradient, Georgia bold title, palace
  motif). The committed `assets/social-preview.png` is the source of
  truth; maintainer uploads it via *Settings → Social preview* for the
  Twitter/Discord link-card.
- ✅ **README ELI5 block** — a "New here? Read this first" section
  between the nav bar and "The Problem" covers Claude Code / Obsidian
  / MCP in plain language, an end-to-end pipeline diagram, the 5-minute
  happy path, and five pre-install FAQs (API cost, Obsidian-optional,
  backend choice, disk footprint, mixed-use vault).
- 🟡 **Pending user action** — social-preview PNG still needs to be
  uploaded to the GitHub repo settings page (*Settings → Social
  preview → Edit → upload `assets/social-preview.png`*). Done once,
  sticks forever.

### Next session starts here

**v0.4.2-alpha batch tamam (2026-04-19 → 20, 17 commit):**

| Commit | Parça |
|---|---|
| `033a7d4` | Phase 1 design spec (skill-first reframe) |
| `c7d6c58` | 4.2.1 mnemos-mine-llm skill + canonical prompt |
| `e300a2c` | 4.2.2 pilot.py orchestrator + CLI (31 test) |
| `777d076` | 4.2.3 + 4.2.5 compare-palaces skill + accept komutu |
| `b8b3b4c` | 4.2.6 real-vault pilot (3 session, 4 finding) |
| `d8cb5c1` | 4.2.7 + 4.2.8 filesystem fallback + pilot-session filter |
| `da85a58` | 4.2.10 latency realism docs |
| `6e00736` | 4.2.9 palace indexer + `mnemos mine --from-palace` |
| `5ef2dac` | 4.2.11 skill prompt multi-format (Type A/B/C/D) |
| `326cc6d` | 4.2.12 orchestrator multi-source plan |
| `a28eb31` | 4.2.13 `--pilot-limit 0` + CLI source breakdown |
| `ad31ff2` | 4.2.14 parallel execution + monitor-friendly progress |
| `d8b233d` | per-source token visibility in progress events |
| `0c55366` | `--model sonnet` pin for skill subprocess |
| `be4a17e` | cumulative token alongside per-source in progress lines |
| `6e8a3e3` | `.gitkeep.md` filter in `_discover_sources` |
| `dbe13da` | 4.2.15 docs — skill-mine accepted, live in kasamd |

**Kasamd canlı durumu (post-accept + 2026-04-21 cleanup):**

- `Mnemos/` = **593 skill-mine drawer** (572 orijinal accept batch +
  21 yeni post-accept session drawer'ı). 5-hall dağılımı:
  decisions 255 / events 156 / problems 148 / preferences 32 /
  emotional 2. 6 wing. Önceki script-mine palace (725 drawer)
  `_recycled/Mnemos-2026-04-20/`'de arşivli.
- `mnemos.yaml: mine_mode: skill`
- `Mnemos/search.sqlite3` 593 drawer'dan rebuilt (sqlite-vec backend)
- `mnemos search` smoke: "safa clutch" / "jzg24c deadline anchor" /
  "v042 alpha accept skill mine" üçü de skill drawer top-1 döndürdü
- Pilot rapor: `kasamd/docs/pilots/2026-04-19-llm-mine-pilot-3.md` —
  5-eksen qualitative judgment dolu

**2026-04-21 hybrid-palace temizliği (root cause + düzeltme):**
- **Sorun:** accept sonrası auto-refine hook SessionStart'ta
  `mnemos mine Sessions/` (regex) çağırıyordu. ID deterministic olsa
  da skill-mine smart-H1 filename ≠ regex section-header filename →
  hiçbir drawer overwrite olmadı, ama 535 regex drawer `facts/` hall
  ve `alınan-kararlar/yapılanlar/özet/sonraki-adımlar/see-also/
  sorunlar` section-header filename pattern'iyle skill palace'ın
  yanında birikti. Frontmatter farkı: skill drawer `source_type:
  skill-mine` taşıyor, regex drawer bu field'ı taşımıyor →
  ayrıştırma güvenli.
- **Fix 1 — hook guard** (`a5042a2`): `mnemos/auto_refine.py`
  `_read_mine_mode(vault)` inline yaml parse ediyor; yaml'da
  `mine_mode: skill` ise regex mine çağrısı skip oluyor. Hook
  sadece refine yapar, mining pilot orchestrator'a bırakılır.
  4 yeni test, auto_refine suite 65/65 green.
- **Fix 2 — vault cleanup** (repo commit yok, kasamd-only):
  535 regex drawer `_recycled/regex-cleanup-2026-04-21/`'e
  taşındı (silme değil); 101 boş hall/room dir temizlendi;
  index rebuild `--from-palace` ile yapıldı.
- **Fix 3 — post-accept iki yeni session skill-mine edildi:**
  `2026-04-19-mnemos-v042-alpha-skill-mine-accept` (13 drawer) +
  `2026-04-21-gyp-deadline-anchor-jzg24c-teknik-uygunluk` (8 drawer).
  Pilot orchestrator `--pilot-limit 0` ile başlatıldı ama ledger
  path mismatch yüzünden tümünü baştan mine etmeye başladı;
  hedef 21 drawer üretildikten sonra durduruldu, sadece iki hedef
  session'ın drawer'ları `Mnemos-pilot/` → `Mnemos/` path-preserving
  kopyalandı, kalan `Mnemos-pilot/` `_recycled/Mnemos-pilot-2026-04-21-partial/`'e
  arşivlendi.
- **Snapshot:** temizlik öncesi `kasamd-Mnemos-backup-2026-04-21-1738.zip`
  (4.4 MB) vault-root'ta duruyor.

Full suite **542 pass / 2 skip / 3 deselect** (+4 hook guard test). Working tree temiz.

### Released — 4.3.A Hook → skill-mine route + catch-up (2026-04-22)

- ✅ **Hook routes to skill-mine when `mine_mode: skill`** — `auto_refine.py`'ın skill-mode guard'ı skip'ten route'a çevrildi. Yeni `_run_skill_pipeline` iki-fazlı queue çalıştırır:
  - **Phase A** (priority): unmined Sessions → `/mnemos-mine-llm` (refine zaten yapılmış, sadece mine kaldı)
  - **Phase B** (main): unrefined JSONLs → worker başına zincir `/mnemos-refine-transcripts` sonra `/mnemos-mine-llm` (refine ledger'ından session_md path'i okunur)
  - Fire-toplam cap **10** (A önce yer doldurur, remainder B'ye)
  - Her subprocess `claude --print --dangerously-skip-permissions` (hook non-interactive)
- ✅ **`mnemos catch-up [--limit N] [--parallel N] [--dry-run] [--yes]`** — foreground bulk processor. `mine_mode: skill` zorunlu, `CatchUpError` aksi halde. `--parallel N` shard-based worker pool (ThreadPoolExecutor). Warning output eğer N > 1.
- ✅ **`<vault>/Mnemos/_processing.xlsx`** — native Excel audit trail. `openpyxl` + `filelock` concurrent-safe. 9 kolon: `source_type, path, refined_at, refine_outcome, mined_at, mined_outcome, drawer_count, tokens, notes`. Obsidian `_` prefix ile gizli, Windows Explorer'da çift-tık → Excel.
- ✅ **Hook log `phase=A` / `phase=B` prefix** — post-hoc debug için.
- ✅ **Yeni dependency** — `openpyxl>=3.1` (pure Python, yaygın).
- ✅ **Kasamd ledger backfill** — 593 skill drawer source'larını `~/.claude/skills/mnemos-mine-llm/state/mined.tsv`'e `palace=kasamd/Mnemos` olarak yazdı (103 unique source). Hook bundan sonra bu session'ları atlar; Mnemos-pilot palace'a yazılan eski ledger satırları zararsız kalır. Backfill sonrası dry-run: Phase A = 2 (gerçek unmined po-556 + `.gitkeep.md` noise).

**Yeni tests (+19):** 5 processing_log, 6 picker/ledger helper, 3 pipeline (A/B/cap), 1 routing (replaced old skip test), 3 catch_up, 2 CLI catch-up. Full suite **561 pass / 2 skip / 3 deselect**.

**Commits (2026-04-22, chronological):**

| Commit | Parça |
|---|---|
| `8a8783a` | T1 `openpyxl>=3.1` dependency |
| `a66e65e` | T2 `mnemos/processing_log.py` (xlsx upsert + filelock) |
| `ff01230` | T3 picker + ledger helpers in `auto_refine.py` |
| `b0e8bdd` | T4 `_run_skill_pipeline` two-phase scheduler |
| `0f291be` | T5 `_run_locked` routing to skill pipeline |
| `79490c3` | T6 `mnemos/catch_up.py` foreground processor |
| `b0f377e` | T7 `mnemos catch-up` CLI subcommand |
| `<T10>`   | T10 ROADMAP + STATUS (this commit) |

**✅ Manual smoke run (2026-04-22):**
- Hook wrapper active-session marker yazıyor ama **spawn ettiği bg
  subprocess sessizce ölüyor** (Windows `DETACHED_PROCESS + stdout=DEVNULL`
  kombinasyonu; import/startup error görünmez kalıyor). Ship-blocker
  değil çünkü manuel `mnemos catch-up` + manuel bg invocation sorunsuz
  çalışıyor. v0.4.1 P8 olarak tracked.
- **Manuel bg run başarıyla Phase A mine çalıştırdı:**
  - `2026-04-21-po-556-deadline-anchor-skill-extract-kaldirildi.md` →
    **6 drawer** (GYP / Satin-Alma-Otomasyonu/po-olusturma/: 2 decisions,
    2 events, 1 preferences, 1 problems). Smart H1, absolute-path source,
    entities temiz (`[Xi'an Yile Technology, po-olusturma]`).
  - `.gitkeep.md` → 0 drawer (skill SKIP, placeholder — beklenildi).
  - Süre: ~3 dk (cap 10 altında, her iki item seri koştu).
- **Palace delta:** 593 → **599 drawer**. 5-hall dağılımı güncel.
- **Xlsx:** `_processing.xlsx` 170 → 163 row (9 temizlik + 1 Phase A
  row-sync). Po-556 tek satırda `mined_outcome=OK, drawer_count=6`.
- **Tespit edilen minor schema bug (P9):** Phase A bir Session md'yi
  işlediğinde xlsx'e yeni `md` row ekliyor, ama o md'nin arkasındaki
  JSONL satırı (backfill'den) güncellenmiyor → aynı iş iki row'da
  görünüyor. Bu smoke'da elle sync ettim; v0.4.1 P9 kalıcı fix.
- **`if picked:` gate bug (`fdb92d8`):** smoke sırasında ortaya çıktı.
  T5 testi `picked=[a]` non-empty ile geçiyordu; production'da
  kasamd backfill sonrası picker sıklıkla `[]` dönünce hook skill
  pipeline'ı stranded bırakıyordu. Fix + regression test shipped.

**Scope-dışı küçük polish (v0.4.1'e taşındı):**
- `_pick_unmined_sessions` ve `_pick_unprocessed_jsonls` `.gitkeep*` + `MEMORY.md` filter'ı (zaten `_discover_sources` pilot'ta var, hook picker'ında yok). Kasamd'de şu an `.gitkeep.md` Phase A picker'a düşüyor; skill SKIP ediyor, zararsız ama noise.
- `mnemos processing-log --rebuild` komutu (xlsx'i iki ledger'dan sıfırdan üret). Ship edildiğinde yeni kullanıcının xlsx'i natural doğar (YAGNI); sadece kasamd/brownfield kurtarma senaryosu için.
- **Ledger/palace reconcile komutu** (`mnemos processing-log repair` veya benzeri). 2026-04-22 kasamd analizinde tespit: wings'te **593 gerçek drawer** var ama skill-mine ledger sadece **516 drawer**'ı accounting içinde (`palace=Mnemos` satırları, sum of column 2). 77 drawer palace'ta fiziksel olarak var ama ledger'a yazılmamış — pilot raporu Finding 2'deki "ledger-skipped; recovered from filesystem" pattern'ının birikmesi. Repair komutu palace frontmatter'ını tarayıp eksik OK satırlarını ledger'a + xlsx'e backfill eder (`count_drawers_for_source` pattern'ı pilot.py'da zaten var).
- **Skill-mine-llm source field path discipline** — SKILL.md'ye "drawer frontmatter'daki `source:` alanı daima absolute path" notu. 2026-04-22 audit'te 3 drawer relative path ile yazılmış (`source: memory/user_profile.md`). Ledger'a düzgün absolute path yaz (pilot runtime'ı cwd-relative değil, skill subprocess cwd farklı olabilir).
- **Legacy corrupt ledger rows cleanup** — refine ledger satır 128 (`C:\Users<TAB>ugrademirors\.claude\...`) + 4 UUID-prefix-kesik satır (satır 58/84/94/111) + eski `palace=Mnemos-pilot` satırları. Hook path-match'te tutmaz, xlsx backfill absolute-path filter'ı ile de temiz; yine de one-liner cleanup STATUS'un Pending user actions maddesini kapatır.

---

### ⏭ SIRADAKİ OTURUM — v0.4.0 Phase 1 kalanı

v0.4.2-alpha kapandı + hybrid-palace cleanup + **4.3.A shipped (2026-04-22)**.
Sıradaki parçalar v0.4.0-final için:

- **4.3 Skill-recall** (~5h) — `/mnemos-recall <query>` user skill +
  `/mnemos-briefing` SessionStart opt-in hook + MCP `recall_mode` yaml
  dinamik instructions. Pattern: vector top-50 → Claude Sonnet judge →
  curated 300-500 kelime context. Skill-mine'ın skill-recall kardeşi;
  rerank burada ediyor (embedding değişmiyor).
- **4.5 Settings TUI** (~2.5h) — `mnemos settings` numbered menu
  (backend / mine-mode / recall-mode / hooks / statusline / languages).
  Fragmanlı komutları tek panel altında topla. i18n TR+EN.
- **4.6 LongMemEval benchmark** (~3h) — S+S combo (script-mine +
  script-recall) ölçüm. Hedef Recall@5 ≥ %93. Skill modları kalitatif
  (pilot raporu) — benchmark sadece baseline.
- **4.7 PyPI release v0.4.0** — version bump, CHANGELOG, wheel+sdist,
  GitHub release. 3.10a pre-release wheel inspection paterni tekrarla
  (skill path'leri package'da mı, --model sonnet hardcode mu vb.).

**Opsiyonel v0.4.1 polish:**
- `.gitkeep*` filter zaten `6e8a3e3`'te eklendi → bir sonraki pilot'ta
  discovery'de hiç çıkmayacak. **Picker'lar hâlâ kapsamıyor** —
  `_pick_unmined_sessions` + `_pick_unprocessed_jsonls` için de aynı
  filter (hook / catch-up akışında `.gitkeep.md` ve `MEMORY.md` sessiz
  düşsün). 2026-04-22 dry-run'ında kasamd'de Phase A'ya `.gitkeep.md`
  girdi.
- Script miner section-header kaçışı ("Özet/Sonraki Adımlar/Yapılanlar
  /Alınan Kararlar/See Also" filename'e sızıyor) — script-mine canlı
  olmasa bile benchmark ve geri dönüş senaryoları için temizlemek iyi
- `mnemos mine --raw-only` (4.2.9 follow-up)
- **Ledger/palace reconcile komutu** — `mnemos processing-log repair`
  veya `mnemos mine --reconcile-ledger`. Palace frontmatter'ını tarar,
  skill-mine ledger'ına eksik OK satırlarını filesystem fallback'tan
  backfill eder, `_processing.xlsx`'i günceller. 2026-04-22 kasamd
  bulgusu: palace'ta 593 drawer, ledger accounting 516 (77 gap =
  pilot raporu Finding 2 "ledger-skipped; recovered from filesystem"
  birikmesi). `mnemos processing-log --rebuild` ile birlikte aynı
  modülde (`mnemos/processing_log.py` command surface genişletmesi).
- **Skill-mine-llm source field absolute-path discipline** —
  `skills/mnemos-mine-llm/SKILL.md` frontmatter şema bölümünde
  `source:` alanının **daima absolute path** olduğunu vurgula + canonical
  prompt'a input path'i kaybetmeden kopyalama talimatı. 2026-04-22 audit:
  3 drawer relative path ile yazılmış (`source: memory/user_profile.md`).
- **Legacy corrupt ledger rows cleanup** — refine ledger satır 128
  (`C:\Users<TAB>ugrademirors\.claude\...`) + 4 UUID-prefix-kesik satır
  + eski `palace=Mnemos-pilot` satırları. Harmless, ama STATUS'taki
  Pending user actions maddesini kapatır.
- **Hook ledger-skip koruması** — `_run_skill_pipeline` Phase B
  sonunda refine skill ledger'ı `OK` yazmadıysa ama `Sessions/`'ta
  yeni md oluştuysa filesystem fallback çağır (pilot.py pattern).
  Plan'da Spec §8'de bu durum "Refine OK ama skill ledger'da session
  path bulunamıyor → filesystem fallback" olarak not edilmişti ama
  implementation'da `_latest_session_for_jsonl is None → ERROR` oluyor.

---

**🟡 Pending user actions:**

- Social-preview PNG → GitHub Settings (tek tıklık; v0.4.0 ship'i
  bloklamıyor)
- Skill-mine ledger'ında legacy 2 pilot-2 row'u + corrupted bash-escape
  row'u kalıntı var (`~/.claude/skills/mnemos-mine-llm/state/mined.tsv`).
  Harmless (path-match'te tutmazlar) ama one-liner cleanup düşünebiliriz.
- Mnemos MCP server şu oturum için kill edildi (accept anında graph.json
  SQLite lock tutuyordu). Bir sonraki Claude Code restart'ında otomatik
  respawn eder, yeni skill palace'ı + yeni ChromaDB'yi kullanır.

### Practical stats (author's vault, 2026-04-22)

- **593 drawers** across 6 wings (GYP, General, LightRAG-PO-Arsivi,
  Mnemos, ProcureTrack, Satin-Alma-Otomasyonu), 5-hall dağılımı
  (decisions:255, events:156, problems:148, preferences:32, emotional:2)
- Mine mode: **skill** — auto-refine hook artık `mine_mode: skill` olduğunda
  `_run_skill_pipeline`'a route oluyor (`0f291be` + T4 scheduler). Kasamd
  skill-mine ledger backfilled (103 unique source), ilk fire'da sadece
  gerçek unmined (po-556) işlenecek.
- Backend: sqlite-vec (`Mnemos/search.sqlite3`), 593 drawer indexed
- 67 refined session notes in `Sessions/` (53 OK from 123 processed transcripts)
- Backlog: **0** — all Claude Code JSONL transcripts processed
- Auto-refine hook processes 3 closed transcripts per new session start
  (bu hook'un içinde skill-mine tetiklenmesi opsiyonel; şimdilik hook hâlâ
  regex-mine çağırıyor — Phase 2 automation'da revizyon olacak)

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
