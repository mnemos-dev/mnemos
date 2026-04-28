# v0.4.0 — AI Boost / Phase 1 (design spec)

**Date:** 2026-04-19
**Status:** Design approved, implementation starting
**Previous version:** v0.3.3 post-v0.3.2 cleanup (released to PyPI 2026-04-19)
**Next version:** v0.5.0 Automation / Phase 2

---

## 1. Problem summary

Phase 0 delivered: with API-less regex + vector search, **90% Recall@5**
on the LongMemEval 10q subset (2026-04-17, parity across both backends).
The goal is to push to 95%; but doing it **without adding API dependency**
is consistent with both our product promise (Obsidian-native, no opaque
system) and the Phase 0 doctrine (*mnemos does not call LLMs*).

**Original ROADMAP 4.1-4.6 (designed in the 2026-04-13 Phase 0 spec):**
- 4.2 API-based LLM mining (`mnemos-dev[llm]` extra + `ANTHROPIC_API_KEY`)
- 4.3 API-based LLM reranking (search top-50 → top-10)
- 4.4 API-based contradiction detection
- 4.5 Benchmark (target R@5 ≥95%)

**Reframing (2026-04-19 discussion, the essence of this spec):**
The `mnemos-refine-transcripts` skill we shipped in v0.3.0 proved that
skills running inside a Claude Code session are a clean way to get LLM
work done outside the mnemos package. No need to package an API; the user
uses their subscription quota; cost is transparent to the user.

We are extending this pattern to mining itself and to recall. Now every
user has **two orthogonal axes:**

| | Script-recall | Skill-recall |
|---|---|---|
| **Script-mine** | (1) Today — fast, API-less, deterministic | (2) Vector + LLM judgment |
| **Skill-mine** | (3) LLM-enriched drawers, fast recall | (4) LLM everywhere — max quality, max latency |

The user starts with a **pilot** (10 sessions are processed in parallel by
both script-mine and skill-mine), compares the two palaces produced on
their own data, decides, and the loser goes to `_recycled/`. Recall mode
can be changed at runtime via `mnemos settings` — post-pilot, all four
combos can live on a single palace.

**4.3 rerank** is not a separate task in this model; skill-recall already
does LLM judgment, and rerank is dissolved into it.

**4.4 contradiction** is an orthogonal concern (hygiene); deferred to v0.5
Automation.

---

## 2. Scope

### In scope

- **4.2 Skill-mine + pilot orchestrator + comparison skill** — new
  `mnemos-mine-llm` skill, `mnemos mine --pilot-llm [N=10]` command,
  produce two palaces side by side, the `mnemos-compare-palaces` skill
  produces an LLM-judged decision report.
- **4.3 Skill-recall** — `/mnemos-recall <query>` user-invoked skill;
  opt-in SessionStart briefing hook (parallel to refine-hook); MCP server
  `instructions` field is generated dynamically from the `recall_mode`
  yaml setting.
- **4.5 `mnemos settings` TUI** — gathers fragmented commands (install-hook,
  install-statusline, migrate, hand-edit yaml) under a single numbered
  menu. Mine-mode, recall-mode, backend, hooks, languages.
- **4.6 LongMemEval benchmark** — quantitative measurement only for the
  S+S (script-mine + script-recall) combo (500-question full run, 4
  modes). Skill modes are qualitative, integrated into the pilot report.
- **4.7 PyPI release v0.4.0**

### Out of scope (v0.5 or later)

- **API-based LLM mining** (`mnemos-dev[llm]` extra) — unnecessary with
  the skill-mine pattern.
- **Rerank as a separate task** — inside skill-recall.
- **Contradiction detection / stale memory flagging** — v0.5 hygiene task.
- **Per-turn auto-recall** (UserPromptSubmit hook) — 5-15s blocking
  latency hurts user experience. SessionStart briefing is enough;
  explicit `/mnemos-recall` covers the remaining user need.
- **Multi-language skill prompts** (Phase 0 has EN+TR marker support but
  skill prompts are written primarily in EN; TR+EN output supported) —
  marker expansion is a v0.6 task.
- **Palace merge** (union of script-mine + skill-mine drawers) — the
  user picks one after the pilot, the other is recycled.

---

## 3. Architectural axis — 4-combo

We refer to this table throughout the spec:

```
                        Script-recall            Skill-recall
                    ┌────────────────────┬────────────────────┐
     Script-mine    │ (1) TODAY          │ (2)                │
                    │ MCP vector search  │ Vector → LLM judge │
                    │ 200-500ms          │ 5-15s              │
                    │ Auto AI query      │ Explicit /recall   │
                    ├────────────────────┼────────────────────┤
     Skill-mine     │ (3)                │ (4) MAX QUALITY    │
                    │ Curated drawers +  │ LLM both ends      │
                    │ fast MCP search    │ Slow but richest   │
                    └────────────────────┴────────────────────┘
```

**Mine-mode** is a single choice per vault (steady-state). **Recall-mode**
is a per-vault yaml setting, can be flipped; the MCP server reads it at
startup.

---

## 4. Task 4.2 — Skill-mine + pilot orchestrator

### 4.2.1 `mnemos-mine-llm` skill

`skills/mnemos-mine-llm/SKILL.md` (repo canonical, junction'd to
`~/.claude/skills/`, following the refine-transcripts pattern).

**Input:** Path of a refined session `.md` file + target palace root
(such as `Mnemos-pilot/`).

**Output:** One or more drawer `.md` files under the target palace. The
skill writes files **directly** — no intermediate JSON/validator (user
decision, 2026-04-19).

**Drawer format** (compatible with the existing palace schema):

```markdown
---
wing: Mnemos
room: phase1-design
hall: decisions
entities: [skill-mine, pilot-orchestrator]
source_path: Sessions/2026-04-19-phase1-design.md
mined_at: 2026-04-19T10:30:00
---

# Skill-mine pilot orchestrator decision

> Source: [[Sessions/2026-04-19-phase1-design]]

The user approved the proposal of a 10-session pilot. Script-mine and
skill-mine will run in parallel and two palaces will be produced...
```

**Prompt design** (within the skill):
- Read the refined session .md
- Inspect the existing palace — collect existing wing/room names (for
  consistency)
- Split exchanges into segments, identify each one's hall (decisions /
  preferences / problems / events / emotional)
- For each significant segment, produce a drawer .md (frontmatter + H1 +
  source wikilink + prose)
- Entity extract (distinguish people / projects, not tags — comply with
  v0.3.2 hygiene rules)
- Wing canonicalization (v0.3.2 TR diacritic normalize is in effect)

**Ledger:** `skills/mnemos-mine-llm/state/mined.tsv` — processed refined
session paths + timestamp + drawer count + palace root. For resume (if
the orchestrator is interrupted).

**Junction:** Same pattern as the refine-skill. Repo canonical, junction
to `~/.claude/skills/mnemos-mine-llm` (Windows) or symlink (Unix). Added
to the architectural-line in CONTRIBUTING.

### 4.2.2 Orchestrator: `mnemos mine --pilot-llm [N]`

**New module:** `mnemos/pilot.py`

**Flow:**

1. **Pre-flight:**
   - Scan the `Sessions/` directory in the vault, list refined session .mds
   - Take the N (default 10) newest (configurable `--limit`)
   - Pre-flight plan: N sessions × ~30s skill call + script mine ~30s
     total = estimated duration
   - Confirm (unless `--yes`)

2. **Set up two palaces:**
   - `<vault>/Mnemos/` — existing (script-mined, palace_root default)
   - `<vault>/Mnemos-pilot/` — new, skill-mined target
   - `Mnemos-pilot/` rebuild lock `<vault>/.mnemos-pilot.lock.flock`
     — prevents a second pilot instance from starting while the pilot is
     running

3. **Script-mine leg:**
   - `mnemos mine Sessions/` runs with existing behavior (not parallel
     — independent of skill-mine, already fast)

4. **Skill-mine leg:**
   - For each session: `claude --print --dangerously-skip-permissions
     --output-format json "/mnemos-mine-llm <session.md> <Mnemos-pilot>"`
   - **v0.4.0-alpha: sequential** (MVP). Parallel-3 will come in v0.4.1.
   - `ANTHROPIC_API_KEY` stripped from subprocess env → subscription auth
   - The `usage` field is parsed from the JSON of each call:
     `{input_tokens, output_tokens, cache_read_input_tokens,
       cache_creation_input_tokens}`
   - Token counters are aggregated
   - **Latency realism:** Per-session wall-clock ~3-5 min (2026-04-19
     kasamd pilot). 100 sessions sequential ~7h, with parallel-3 ~2.5h.
     The spec's old "25s/session" estimate turned out 10x off (pilot
     Finding 1).

5. **Index skill-mined drawers:**
   - `mnemos mine Mnemos-pilot/ --palace-root Mnemos-pilot` — the
     existing miner reads drawer .mds and writes them to the
     ChromaDB/sqlite-vec index
   - The skill already did the semantic work; the miner only does
     embedding + metadata parse, doesn't re-run pattern classification (a
     new flag `--skip-classification` will be added; drawer frontmatter
     is authoritative)

6. **Generate pilot report:**
   - Skeleton at `<vault>/docs/pilots/2026-MM-DD-llm-mine-pilot.md`
   - Script-mine: N drawers, H halls, E entities, duration X sec, 0 tokens
   - Skill-mine: N' drawers, H' halls, E' entities, duration Y sec, T
     total tokens (input I, output O, cache R)
   - For 3 random sessions, side-by-side diff of drawers (what the
     script side vs the skill side extracted from the same session)
   - Placeholder at the end of the report: *"Run `/mnemos-compare-palaces`
     to fill in the qualitative judgment."*

7. **Orchestrator done:** tell the user the next steps:
   ```
   Pilot complete. Review:
     docs/pilots/2026-04-19-llm-mine-pilot.md

   Next:
     1. /mnemos-compare-palaces           → LLM judgment report
     2. mnemos pilot --accept script      → keep script-mine, recycle Mnemos-pilot/
     3. mnemos pilot --accept skill       → keep skill-mine, move Mnemos-pilot/ to Mnemos/
     4. mnemos pilot --keep-both          → (not recommended — see spec §3)
   ```

### 4.2.3 `mnemos-compare-palaces` skill

`skills/mnemos-compare-palaces/SKILL.md`

**Input:** the two palace root paths + the pilot report skeleton

**Flow:**
- Read drawers from both palaces for the same 10 source sessions
- Collect size/count metrics (drawer count, hall distribution, entity
  overlap, average drawer body length)
- Side-by-side analysis for 3 sample sessions:
  - Which is richer? (drawer count, semantic coverage)
  - Which is cleaner? (noise, junk drawers, entity garbage)
  - Is the hall classification more consistent?
  - Is the drawer body readable on its own?
  - Are the wikilinks correct?
- The LLM writes its own judgment but leaves the decision to the user:
  *"Skill-mine appears to surface 40% more emotional-hall segments but
  also produces 15% more low-confidence drawers. If emotional context
  matters to your recall usage, skill-mine wins; if you want tighter
  deterministic drawer sets, script-mine. You decide."*
- Fills in the pilot report skeleton

**Ledger:** none — user-invoked one-shot.

### 4.2.4 Token accounting

Output of Claude Code's `claude --print --output-format json` after each
call:
```json
{
  "type": "result",
  "result": "...",
  "usage": {
    "input_tokens": 3240,
    "output_tokens": 1820,
    "cache_read_input_tokens": 0,
    "cache_creation_input_tokens": 2100
  }
}
```

For each pilot call, the orchestrator parses this field and writes the
aggregated total into the report. For subscription users it is reported
as "**subscription quota** usage" rather than "$0" — we don't estimate
metered prices (we don't know the user's plan). For transparency, an
`--estimate-cost` flag using a Sonnet 4.6 price template (`$3/M input +
$15/M output`) could be added (nice-to-have, not in scope; if
implementation is easy, the pilot orchestrator may include it).

### 4.2.5 `mnemos pilot --accept <mode>`

- `--accept script`: `Mnemos-pilot/` → `_recycled/Mnemos-pilot-YYYY-MM-DD/`
- `--accept skill`:
  1. `Mnemos/` → `_recycled/Mnemos-script-YYYY-MM-DD/`
  2. `Mnemos-pilot/` → `Mnemos/`
  3. Write `mine_mode: skill` in `mnemos.yaml`
  4. ChromaDB/sqlite-vec index rebuild (so new drawers reflect the
     current palace root)
- Both update `.mnemos-pending.json` with a `pilot_completed_at`
  timestamp.

---

## 5. Task 4.3 — Skill-recall

### 5.1 `mnemos-recall` skill

`skills/mnemos-recall/SKILL.md`

**Input:** Query string (typed by the user, or extracted from session
context)

**Flow:**

1. **Fast vector filter:** Skill calls subprocess `python -m mnemos.cli
   search "<query>" --limit 50 --format json --vault <v>`. Not the
   script-recall MCP tool, the CLI — the skill's internal call.
2. **LLM judgment:** The top-50 drawers' title + first 200 chars +
   metadata are placed in the prompt. The LLM is asked: "Which 10
   drawers are actually relevant to this query?"
3. **Full body read:** Read the full body of the chosen 10 drawers.
4. **Curate:** Write a 300-500 word context briefing — wikilinks point
   to source drawers so the user can follow up.
5. Print to stdout. Since the skill is user-invoked, it injects directly
   into the Claude Code session.

**Latency:** 5-15s (vector search <1s, LLM judgment 3-10s, full read 1s,
curate 1-3s). User waits explicitly.

**Usage:**
```
/mnemos-recall "gyp purchasing automation latest status"
/mnemos-recall "what was the phase1 rerank decision"
```

### 5.2 SessionStart briefing hook (opt-in)

**Goal:** A user running in skill-recall mode should see a "what you
worked on in the last week" summary on every session open, without
having to invoke explicit `/mnemos-recall`.

**New module:** `mnemos/recall_briefing.py`

**Flow** (parallel to the refine-hook pattern):

1. SessionStart hook fires
2. Wrapper non-blocking background spawn:
   `claude --print --dangerously-skip-permissions --output-format json
   "/mnemos-briefing"`
3. The skill reads the `briefing_projects: [...]` hint in
   `<vault>/mnemos.yaml` (if empty, automatically picks wings with
   activity in the last 7 days)
4. For the chosen wings, reads the title + hall + entities list of the
   last 10-20 drawers
5. Reads the first paragraphs of the last 3 `Sessions/*.md` files (what
   was being worked on)
6. LLM writes a 200-300 word briefing:
   - Active projects: `[[Mnemos]]`, `[[GYP]]`
   - Last 48-hour decisions: ...
   - Open issues: ...
   - Up next: ...
7. Writes to `<vault>/.mnemos-briefing.md` (prev → prev-prev rotate)

**Context injection** (single design choice, two alternatives):

**Alt-A: Stale-but-fresh model** (recommended for v0.4)
- If a SessionStart hook briefing FILE EXISTS + is fresh (<4h), inject
  via `additionalContext`
- Otherwise no injection, background regenerate (so it's ready for the
  next session)
- Briefing visible from the 2nd session onwards

**Alt-B: Blocking fresh model** (can be deferred to v0.5)
- SessionStart blocks 10-15s, generates a current briefing every time
- Clean but with a latency cost

**v0.4 picks Alt-A.** Fits the refine-hook's `last_outcome` idle-render
pattern.

**CLI:** `mnemos install-recall-hook` (idempotent, same shape as
install-hook), `mnemos install-recall-hook --uninstall`.

**Skill:** `skills/mnemos-briefing/SKILL.md` (separate from the recall
skill — this is cron-like auto, recall is user-invoked).

### 5.3 MCP server `instructions` — recall_mode-aware

The current MCP server (`mnemos/__main__.py` or `mnemos/server.py`) has a
static `instructions` field:
> "At the START of every session, call mnemos_wake_up..."

`recall_mode` will be read from `mnemos.yaml` and the field generated
dynamically:

- `recall_mode: script` (default): existing instruction — AI auto-calls
  `mnemos_search` when relevant. Potentially every turn.
- `recall_mode: skill`: instruction changes:
  > "The user prefers skill-based recall. Do NOT call `mnemos_search`
  > unless the user explicitly asks. Session-start briefing is already
  > injected as context; user will invoke `/mnemos-recall` for on-demand
  > queries."

All tools remain exposed — the skill uses search internally.

---

## 6. Task 4.5 — `mnemos settings` TUI

**New module:** `mnemos/settings_tui.py`

**Behavior:**

- Numbered menu (continuation of the init pattern, not curses —
  platform-agnostic)
- i18n TR+EN (add keys to existing `mnemos/i18n.py`)
- `mnemos.yaml` canonical store
- Each row shows the current state + action affordance
- Tasks like reset hook, install hook open a sub-prompt
- Windows cp1252 compatible (conftest fix is in effect)

**Skeleton:**

```
╭────────────────────────────────────────────────────────╮
│  mnemos settings  —  vault: ~/.../kasamd              │
├────────────────────────────────────────────────────────┤
│  1. Backend          chromadb (620 MB · 683 drawers)  │
│  2. Mine mode        script                           │
│  3. Recall mode      script                           │
│  4. Refine hook      ✅ installed                     │
│  5. Recall hook      ❌ not installed                 │
│  6. Statusline       ✅ installed                     │
│  7. Languages        tr, en                           │
│  8. Briefing hint    (auto-detect recent activity)    │
│  9. Vault            ~/.../kasamd   (read-only)       │
├────────────────────────────────────────────────────────┤
│  Press number to change, q to quit.                   │
╰────────────────────────────────────────────────────────╯

> _
```

**Sub-behavior of each row:**

| # | Action |
|---|---|
| 1 | Submenu: "migrate to sqlite-vec" / "migrate to chromadb" / "cancel" — delegates to `mnemos migrate` |
| 2 | "run pilot (10 sessions)" / "switch to skill (no pilot)" / "cancel" |
| 3 | Toggle script ↔ skill + warn "restart Claude Code for MCP to pick up new mode" |
| 4-6 | Install / uninstall / refresh — delegates to existing install-* commands |
| 7 | Comma-separated edit, yaml valid langs subset |
| 8 | Edit briefing_projects list; default empty = auto-detect |
| 9 | Read-only display |

**Separate commands** (`mnemos install-hook`, `mnemos migrate`, etc.) **do
not go away** — the settings TUI is a thin wrapper on top of them. CLI
automation scripts continue to work.

---

## 7. Task 4.6 — Benchmark

LongMemEval full 500 questions, 4 modes — but now **only for the S+S
combo**. Skill-recall is qualitative and cannot be benchmarked (each run
has different LLM judgment; not deterministic).

**Run:**
```bash
mnemos benchmark longmemeval --limit 500 --mode combined
```

**Target:** R@5 ≥ **93%** (marginal improvement over Phase 0's 90%; the
skill-mine pilot can boost drawer quality, but since the S+S combo uses
script-mine, the main effect will come from 4.2 drawer hygiene fixes).

**Note:** The original Phase 0 spec targeted 95%+; the +5% boost from
API-based rerank was expected. In the skill-first approach, rerank
doesn't touch the S+S combo — the user gets the rerank benefit by
choosing skill-recall (no benchmark, qualitative). The target was
therefore lowered to 93%. Our 95% claim is dropped; the new claim in
Phase 1 is: *"deterministic-but-improving score above 90% + optional
LLM-driven qualitative upgrade."*

---

## 8. Task 4.7 — PyPI release v0.4.0

Standard release routine (v0.3.x patterns):

- Version bump `0.3.3 → 0.4.0` (`pyproject.toml` + `mnemos/__init__.py`)
- `CHANGELOG.md` — Phase 1 summary, 4 new skills, pilot flow, settings
  TUI, no breaking changes
- `STATUS.md` §2 current — skill-mine capability, skill-recall capability,
  mnemos settings, briefing hook, pilot orchestrator
- `ROADMAP.md` — 4.2-4.7 checkboxes `[x]`
- Wheel + sdist build
- Pre-release inspection (3.10a pattern): are skill paths shipped as
  package-data in the wheel? Are skill files under
  `mnemos/_resources/skills/`? Is the junction/symlink install script
  exposed as the CLI `install-skills` command?
- Tag `v0.4.0` (annotated), GitHub release (with assets)
- PyPI upload (delegated to user, standard)

---

## 9. File list

**New modules:**
- `mnemos/pilot.py` — orchestrator
- `mnemos/recall_briefing.py` — SessionStart briefing hook wrapper
- `mnemos/settings_tui.py` — interactive settings panel

**New skills:** (all junction'd, repo canonical)
- `skills/mnemos-mine-llm/` — SKILL.md + prompt + state ledger directory
- `skills/mnemos-recall/` — SKILL.md + prompt
- `skills/mnemos-briefing/` — SKILL.md + prompt (auto-invoked by hook)
- `skills/mnemos-compare-palaces/` — SKILL.md + prompt

**Changed modules:**
- `mnemos/cli.py` — new subcommands: `mine --pilot-llm`, `pilot
  --accept`, `settings`, `install-recall-hook`
- `mnemos/miner.py` — `--skip-classification` flag (trust the
  skill-mined drawer frontmatter)
- `mnemos/server.py` (or `mnemos/__main__.py`) — `instructions` dynamic,
  read from `recall_mode`
- `mnemos/i18n.py` — new keys (settings TUI, pilot flow, briefing)
- `mnemos/config.py` — new yaml fields: `mine_mode`, `recall_mode`,
  `briefing_projects`

**New test files:**
- `tests/test_pilot.py` — orchestrator happy path, two palace
  concurrency, accept logic, rollback on failure
- `tests/test_recall_briefing.py` — hook wrapper, stale file logic,
  blocking-model negative test
- `tests/test_settings_tui.py` — numbered menu navigation, yaml
  roundtrip, submenu delegation
- `tests/test_skill_mine_integration.py` — fake-claude subprocess mock
  (deterministically simulate skill output)
- `tests/test_mcp_instructions_mode.py` — instruction string changes
  when recall_mode changes

---

## 10. Implementation order

| Order | Task | Estimated time |
|------|-------|--------------|
| 1 | 4.2.1 mnemos-mine-llm skill — SKILL.md + prompt | 2h |
| 2 | 4.2.2 Orchestrator `pilot.py` + CLI subcommand | 3h |
| 3 | 4.2.3 Compare-palaces skill | 1.5h |
| 4 | 4.2.5 `mnemos pilot --accept` | 1h |
| 5 | Real-vault pilot (author's kasamd, 10 sessions) | 1h (live test) |
| 6 | 4.3.1 mnemos-recall skill | 2h |
| 7 | 4.3.2 briefing hook + `install-recall-hook` | 2.5h |
| 8 | 4.3.3 MCP server instructions mode-aware | 30m |
| 9 | 4.5 Settings TUI | 2.5h |
| 10 | 4.6 Benchmark S+S full 500q | 1h (automated, +2h verify) |
| 11 | 4.7 Release prep + pilot-in-pilot (clean-vault) | 2h |

Total **~19h** of active work, +2-3 days of pilot/validation drag. Phase 0
(v0.2) was ~40h; Phase 1 is half that — the skill-first approach
shortens package engineering (no API client, retry logic, rate limiter,
cost estimator, optional extra packaging).

---

## 11. Success criteria

- [ ] `mnemos-mine-llm` skill successfully completes a 10-session pilot
  (ledger resume, parallel-3 spawn, token accounting makes it into the
  report)
- [ ] `mnemos mine --pilot-llm` produces two palaces side by side, the
  pilot report skeleton is written to `docs/pilots/`
- [ ] `/mnemos-compare-palaces` completes the skeleton with an LLM
  judgment report + 3 side-by-side samples
- [ ] `mnemos pilot --accept skill` moves the losing palace to
  `_recycled/`, yaml update, index rebuild atomic
- [ ] `/mnemos-recall "<query>"` returns a curated 300-500 word context
  within 5-15s, wikilinks valid
- [ ] SessionStart briefing hook injects `additionalContext` if the
  fresh `.mnemos-briefing.md` is <4h, otherwise silent + background
  regenerate
- [ ] `mnemos settings` TUI opens an 8-row menu, delegates to the right
  sub-action under each row, yaml roundtrip clean
- [ ] When recall mode changes in the yaml, the MCP server instructions
  update dynamically (after a Claude Code restart, the AI auto-query
  behavior changes)
- [ ] On the LongMemEval 500q S+S combo, Recall@5 ≥ **93%**
- [ ] Existing 463 tests not broken, ~50 new tests added all green
- [ ] Clean-vault pilot (throwaway) full flow green: init → mine →
  pilot-llm → compare → accept → recall → briefing-hook
- [ ] PyPI v0.4.0 wheel contains all skill paths + new modules (the
  3.10a package-data regression has not recurred)

---

## 12. Open questions / things to revisit

1. **Briefing hook freshness window** — is 4 hours appropriate? To be
   measured during pilot. If too short, regenerate every session; if
   too long, stale context.
2. **Skill prompt versioning** — if the prompt changes, existing
   skill-mined drawers are from the old prompt version. New drawers come
   from the new prompt; do we need versioning? Skip for the first
   release, revisit in v0.4.1.
3. **Palace merge option** — what if a "keep both" request comes up
   despite the pilot being well received? Out of spec, but if
   implementation is easy a `mnemos pilot --keep-both` flag could be
   added; UI-level note recommended.
4. **Token cost estimator flag** — Sonnet 4.6 price template + estimated
   cost. Nice-to-have. Can be added quickly; decide before release.
5. **Briefing skill input size** — last 10-20 drawers + 3 session
   paragraphs ~5K tokens. Briefing output 300-500 words ~700 tokens.
   ~6K tokens per skill call. Once per session. Acceptable; but if the
   briefing regenerates often, cumulative cost should be visible —
   should briefing meta be displayed in the statusline?

---

**Doc owner:** Tugra Demirors
**Review:** self (single-maintainer project)
**Next:** this spec is approved; implementation starts at 4.2.
