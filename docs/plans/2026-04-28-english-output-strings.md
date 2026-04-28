---
title: English-Only Output Strings (with TR back-compat)
date: 2026-04-28
status: Plan ready, implementation pending
target_version: v1.2.0
preceded_by: docs/specs/2026-04-26-v1.1.0-sessionend-driven-memory-design.md
---

# v1.2.0 — English-Only Output Strings (Implementation Plan)

## 1. Goal

An English-speaking user (e.g. an American Claude Code user) installs Mnemos
and never encounters a Turkish word or section header — neither in the
GitHub repo nor in any file Mnemos writes into their vault.

**Concretely:**

- New `Sessions/<date>-<slug>.md` notes use English section headers
  (`## Summary`, `## Decisions`, …)
- New `_identity/L0-identity.md` profiles use English schema
  (`## Working Style`, `## Technical Preferences`, …)
- Briefing output template emits English labels
  (`**Current State:**`, `**Active Decisions:**`, …)
- Existing Turkish vault content (the maintainer's `kasamd` vault, plus
  any other early adopter) remains parseable — the briefing skill, the
  identity refresh skill, and any Python parser must accept BOTH
  languages on read

## 2. Strategy: Dual-Match

Three options were considered:

| Option | Description | Cost | Verdict |
|---|---|---|---|
| Hard cut | Switch all writes + reads to EN; user runs migration on their vault | Low impl, breaks existing vaults until migration | ❌ rejected — disruptive |
| **Dual-match** | **Skill prompts emit EN-only; consumers accept TR\|EN** | **Medium impl, zero migration required** | **✅ chosen** |
| Locale-aware | Skill prompts read `cfg.languages` and emit accordingly; consumers accept either | Higher impl, multi-language correct | ⏭ deferred — out of scope; can layer on top later |

### Why dual-match

1. **No user migration required.** Existing TR Sessions and L0-identity files
   in `kasamd` keep working with no action from the user.
2. **Single-format authoring.** Skill prompts write English only — no
   prompt-time language branching.
3. **Localized to a few seams.** Only places that regex-match a section
   header need updating; LLM-driven skills already understand both
   languages from context.
4. **Future-proof.** A locale-aware layer can be added later without
   rewriting the dual-match code.

## 3. Format String Mapping

Authoritative TR → EN translations. These are the strings prompts will
emit and tests will assert against.

### 3.1 Refined Session Schema (`Sessions/<date>-<slug>.md`)

Produced by `skills/mnemos-refine-transcripts` via canonical prompt
`docs/prompts/refine-transcripts.md`.

| TR (current) | EN (new) |
|---|---|
| `## Özet` | `## Summary` |
| `## Alınan Kararlar` | `## Decisions` |
| `## Yapılanlar` | `## Done` |
| `## Sonraki Adımlar` | `## Next Steps` |
| `## Sorunlar` | `## Problems` |
| `## Notlar` (rare) | `## Notes` |

### 3.2 Identity Layer Schema (`_identity/L0-identity.md`)

Produced by `mnemos identity bootstrap` and updated by
`mnemos identity refresh` (skill `mnemos-identity-refresh`).

| TR (current) | EN (new) |
|---|---|
| `## Çalışma stili` | `## Working Style` |
| `## Teknik tercihler (yürürlükte)` | `## Technical Preferences (Active)` |
| `## Reddedilen yaklaşımlar (anti-pattern)` | `## Rejected Approaches (Anti-Patterns)` |
| `## Aktif projeler` | `## Active Projects` |
| `## Yörüngedeki insanlar` | `## People in Orbit` |
| `## Ustalaşmış araçlar` | `## Mastered Tools` |
| `## Revize edilen kararlar (zaman ekseni)` | `## Revised Decisions (Timeline)` |

### 3.3 Briefing Output Template

Produced by `skills/mnemos-briefing` (v3 prompt). Briefing is what
SessionStart injects into Claude's context.

| TR (current) | EN (new) |
|---|---|
| `**Aktif durum:**` | `**Current State:**` |
| `**Geçerli kararlar:**` | `**Active Decisions:**` |
| `**Açık uçlar:**` | `**Open Threads:**` |
| `**Revize/iptal edilen kararlar:**` | `**Revised/Cancelled Decisions:**` |

### 3.4 Miner Heuristic Phrases (out of scope)

`docs/prompts/mine-llm.md` lists Turkish heuristic phrases (`hata`,
`tamamlandı`, `X'e karar verdik`, etc.) that the v0.x cancelled mining
pipeline detected. Since the mining pipeline was deleted in the v1.0
narrative-first pivot, these phrases are no longer used at runtime. They
remain in the historical doc for archaeology only. **No action required.**

## 4. Consumer Audit (where these strings are matched)

Grep results (executed 2026-04-28):

### Production code (`mnemos/`)

| File:Line | String | Role |
|---|---|---|
| `mnemos/recall_briefing.py:590-591` | `"Geçerli kararlar"`, `"Revize/iptal edilen kararlar"` | Inside `CROSS_CHECK_DIRECTIVE` constant — instructions to Claude about which briefing sections to cross-check |
| `mnemos/identity.py:179` | `"Revize edilen kararlar"` | Docstring/comment about identity profile section |

**No Python regex parsers** match section headers — the skills are
LLM-driven and read the markdown with context. The only places these
strings appear in code are the directive constant and a docstring.

### Tests (`tests/`)

| File | Lines | Role |
|---|---|---|
| `tests/test_recall_briefing.py` | ~30 occurrences | Test fixtures using `**Aktif durum:**` as briefing body literal |
| `tests/test_identity.py` | 20–26, 66, 168, 175 | Asserting bootstrap output contains TR section names; using TR headers in test fixtures |
| `tests/conftest.py` | 66, 72 | Session fixture using `## Alınan Kararlar` and `## Sonraki Adımlar` |
| `tests/test_briefing_prompt_v3.py` | 22 | Asserting prompt mentions "Revize" or "Revision marking" |

### Markdown (`skills/`, `docs/prompts/`)

All affected files. These were translated to English prose in the prior
pass, but the OUTPUT TEMPLATES inside them still emit TR headers and need
updating — this is the heart of Phase 3.

## 5. Files to Modify

### 5.1 Skill prompts (output side)

- `docs/prompts/refine-transcripts.md` — change output template Sessions schema
- `skills/mnemos-refine-transcripts/SKILL.md` — update doc references (if any)
- `skills/mnemos-briefing/prompt.md` — change output template briefing schema
- `docs/prompts/identity-bootstrap.md` — change L0-identity output schema
- `docs/prompts/identity-refresh.md` — change L0-identity output schema
- `skills/mnemos-identity-refresh/prompt.md` — change L0-identity output schema

### 5.2 Production code

- `mnemos/recall_briefing.py` — update `CROSS_CHECK_DIRECTIVE` for dual-match (see §6.4 for approach)
- `mnemos/identity.py` — update docstring at line 179

### 5.3 Tests

- `tests/test_recall_briefing.py` — flip primary fixtures to EN; add at least one TR-input back-compat test
- `tests/test_identity.py` — flip primary expectations to EN; add at least one TR-input back-compat test
- `tests/conftest.py` — flip session fixture to EN (or add EN fixture alongside)
- `tests/test_briefing_prompt_v3.py:22` — update reference

### 5.4 Documentation

- `STATUS.md` — note v1.2.0 introduces English-default schema with TR back-compat
- `CHANGELOG.md` — v1.2.0 entry
- `HISTORY.md` — optional brief mention of the polish step
- `docs/ROADMAP.md` — mark v1.2 task done when complete

## 6. Implementation Plan (TDD-friendly)

13 tasks across 7 groups. Each task: write failing test first, minimal
impl, green, commit.

### Group F1 — Set the contract (1 task)

**F1.1** — Add `tests/test_output_strings.py` with paired TR/EN constants
and a regex helper. *(Optional — only if a constants module is needed.
For dual-match in just two places, may be simpler to inline.)*

**Decision point:** Skip F1 if implementation is small enough to inline
the dual-match in the two consumer files. Lean toward inline for v1.2;
revisit if a third consumer appears.

### Group F2 — Refined Session schema (3 tasks)

**F2.1** — Update `docs/prompts/refine-transcripts.md` output template:
swap `## Özet`, `## Alınan Kararlar`, `## Yapılanlar`, `## Sonraki Adımlar`,
`## Sorunlar` → English. Update LANGUAGE rule from "Default: Turkish body"
to "Default: English body" (or "Match transcript dominant language;
default English if mixed").

**F2.2** — Update `skills/mnemos-refine-transcripts/SKILL.md` to mention
the English schema in its sample output.

**F2.3** — Manual smoke test: refine an arbitrary JSONL → verify the
output `Sessions/.md` uses English headers. Junction zero-drift test
should still pass (the canonical prompt is what changed; the SKILL.md
references it).

*(No Python tests need updating here — the refine pipeline doesn't
regex-parse the output; downstream readers handle it.)*

### Group F3 — Identity Layer schema (4 tasks)

**F3.1** — Update `docs/prompts/identity-bootstrap.md` output template
schema (7 section headers).

**F3.2** — Update `docs/prompts/identity-refresh.md` output template +
the `"Reddedilen yaklaşımlar"` reference at line 56 (according to the
prior agent report) → update to English.

**F3.3** — Update `skills/mnemos-identity-refresh/prompt.md` template +
classification examples that reference section names.

**F3.4** — Update `mnemos/identity.py:179` docstring + `tests/test_identity.py`
expectations:

```python
# tests/test_identity.py around lines 20-26
EXPECTED_HEADERS = [
    "Working Style",
    "Technical Preferences",
    "Rejected Approaches",
    "Active Projects",
    "People in Orbit",
    "Mastered Tools",
    "Revised Decisions",
]

# Add one back-compat test:
def test_existing_tr_identity_still_parseable():
    """Verifies that an L0-identity.md with TR headers (legacy from v1.0)
    is still readable by the identity refresh skill — no Python parser
    breaks on TR sections."""
    profile_text = "## Çalışma stili\n- (general) ...\n## Teknik tercihler\n..."
    # Assert no parser raises; identity show / refresh can render it.
```

### Group F4 — Briefing template + cross-check directive (4 tasks)

**F4.1** — Update `skills/mnemos-briefing/prompt.md` v3 output template:
swap all four labels (`**Aktif durum:**` → `**Current State:**`, etc.).
Also update the prompt's "Start directly with `**Aktif durum:**`"
instruction line to the English equivalent.

**F4.2** — Update `mnemos/recall_briefing.py:CROSS_CHECK_DIRECTIVE`. Two
sub-options (pick one in implementation):

```python
# Option A — generic phrasing (preferred, language-agnostic)
CROSS_CHECK_DIRECTIVE = """[MNEMOS BRIEFING — CRITICAL READING INSTRUCTION]

This briefing reflects the user's CURRENT decisions for this project.
If the user's request CONTRADICTS any active decision listed in the
briefing, or any item explicitly marked as revised or cancelled,
PAUSE before acting. Politely ask:
  "This conflicts with your decision <item> from <date> — do you want
   to revise that decision now, or am I misunderstanding?"

Do NOT silently follow contradictory requests.

[BRIEFING CONTENT FOLLOWS]
"""

# Option B — list both languages explicitly
# (more brittle but explicit; not recommended)
```

**F4.3** — Update `tests/test_recall_briefing.py`. Flip primary fixtures
to EN (`**Aktif durum:**` → `**Current State:**` — about 30 occurrences).
Add one back-compat test that feeds a TR-headered briefing cache and
asserts the directive still works (no Python regex breaks).

**F4.4** — Update `tests/conftest.py` session fixture (TR `## Alınan
Kararlar` / `## Sonraki Adımlar` → EN equivalents). Add a TR fixture
alongside if back-compat coverage is wanted.

**F4.5** — Update `tests/test_briefing_prompt_v3.py:22` to assert
"Revision marking" only (drop the `or "Revize"` fallback) — but keep
asserting the directive logic works on TR-headered briefings via a
separate test.

### Group F5 — Documentation (3 tasks)

**F5.1** — Update `STATUS.md` §2 capability list: note that `Sessions/`
and `L0-identity.md` now use English schema by default; back-compat
preserves TR vaults.

**F5.2** — Update `CHANGELOG.md` v1.2.0 entry under a new top-of-file
section. Headline: "English-default output schema with Turkish back-compat".

**F5.3** — Update `docs/ROADMAP.md` to add the v1.2.0 row (status: in
progress / shipped). Optional: amend `HISTORY.md` "What's next" section
to mark v1.2 as the polish that took the experience to fully-English.

### Group F6 — Verification (3 tasks)

**F6.1** — Full pytest pass. Target: ≥527 tests pass (current baseline +
new back-compat tests should add a handful).

**F6.2** — Junction zero-drift verification (the existing test
`test_skill_identity_refresh.py` etc. should already cover this; just
run the test suite).

**F6.3** — Empirical smoke test on kasamd:
- Open new Claude Code session in any project cwd
- Have a real exchange (≥3 turns)
- `/exit`
- Verify the new `Sessions/<date>-<slug>.md` uses English headers
- Open a new session in the same cwd → briefing renders correctly
  with `**Current State:**` etc.
- Run `mnemos identity refresh --vault "<kasamd>"` — verify it parses
  the existing TR `L0-identity.md` without error and that any new
  delta entries appear under English headers (e.g. new "Revised
  Decisions" entry below the existing "Revize edilen kararlar" entries
  — or, ideally, the refresh moves them all under EN headers; this is
  a design choice, see §7).

### Group F7 — Optional migration helper (3 tasks, defer if v1.2 ships clean)

**F7.1** — `mnemos migrate-headers --vault PATH [--dry-run]` CLI command.
Walks `Sessions/*.md` and `_identity/L0-identity.md`, renames TR
headers to EN. Idempotent.

**F7.2** — Tests for the migration: round-trip on a synthetic vault
(create TR-headered files, run migrate, assert all headers EN, no
content lost).

**F7.3** — Document in `README.md` migration section + `CHANGELOG.md`.

## 7. Open Design Question — Mixed-Language Identity File

When `mnemos identity refresh` runs against a vault with an existing
TR `L0-identity.md`, what does the new content go under?

**Option A** — Append new content under EN headers, leave TR headers
untouched. Result: a hybrid file with both languages. Functionally
correct (refresh skill is LLM-driven and understands either) but
visually inconsistent.

**Option B** — On refresh, rewrite the file fully in EN (lossy
translation, since the skill rewrites the body anyway). User loses
the original TR phrasing.

**Option C** — Add a `mnemos migrate-headers` step (Group F7) that the
user runs once before the first EN refresh.

**Recommendation:** Option C with documentation. The migration is
optional and clearly communicated. New users start in EN; existing
TR users are nudged toward migration but not forced.

## 8. Risk and Rollback

### Risks

- **Skill prompts produce English even for Turkish users.** Acceptable
  intent: this is the explicit project goal. Existing Turkish users can
  use the migration helper (F7) or accept English from this point
  forward.
- **Existing TR briefing cache files** (`<vault>/.mnemos-briefings/*.md`)
  contain `**Aktif durum:**` literals. The cache TTL or readiness gate
  will eventually invalidate them; until then, briefings might still
  display TR labels. Acceptable — caches refresh organically.
- **Test coverage gap.** Dual-match logic in `CROSS_CHECK_DIRECTIVE` is
  passive (it's a directive to Claude, not regex). Coverage is via the
  empirical smoke (F6.3).

### Rollback

`git revert` the merge commit. All changes are localized to docs,
prompts, and ~5 lines of Python. Reversal is mechanical.

## 9. Acceptance Criteria

- [ ] All canonical prompts (refine, briefing, identity-bootstrap,
      identity-refresh) emit English-only schema in their output
      templates
- [ ] `mnemos/recall_briefing.py:CROSS_CHECK_DIRECTIVE` uses
      language-agnostic phrasing
- [ ] Test suite passes ≥527 tests with at least one explicit TR
      back-compat test per affected schema (3 schemas × 1 test each =
      3 new tests)
- [ ] Empirical smoke test on author's kasamd vault: new Sessions in
      EN, briefing renders with EN labels, identity refresh accepts
      existing TR L0-identity.md without error
- [ ] STATUS.md, CHANGELOG.md, ROADMAP.md updated
- [ ] No Anthropic API calls (CI grep still passes)
- [ ] Zero-drift skill junction tests still pass

## 10. Resume protocol — what to do when this plan is picked up

When the next session starts:

1. Read this plan top-to-bottom (you are here)
2. Confirm scope hasn't drifted: re-grep for the format strings in §3
   to see if any new consumers appeared since 2026-04-28
3. Start with Group F1 (or skip if inlining feels right). Otherwise
   start at F2.1.
4. Work group-by-group in order. Commit after each group passes
   tests.
5. Group F7 (migration helper) is optional — ship the core change
   first, decide on F7 based on whether anyone is asking for it.

Use `superpowers:executing-plans` or work through inline. The
implementation should fit comfortably in one focused session
(~3-5 hours estimated for F1-F6; F7 is another 2 hours).

## 11. Estimated effort

| Group | Tasks | Estimate |
|---|---|---|
| F1 | 0–1 | 30 min (or skipped) |
| F2 | 3 | 45 min |
| F3 | 4 | 60 min |
| F4 | 5 | 90 min |
| F5 | 3 | 30 min |
| F6 | 3 | 45 min (incl. empirical smoke) |
| F7 (optional) | 3 | 90–120 min |
| **Total core (F1-F6)** | **15–16** | **~5 hours** |
| **Total with F7** | **18–19** | **~7 hours** |

## 12. Definition of done

- v1.2.0 tag pushed
- CHANGELOG entry shipped
- Empirical smoke green on kasamd (EN new + TR back-compat)
- README "What you'll see in your vault" example updated to show EN
  headers
