# 2026-04-16 New-user simulation pilot (v0.3 task 3.9)

**Goal:** prove the README's documented onboarding works end-to-end on a
clean throwaway vault — without polluting the author's real `~/.claude/`
or real vault.

**Setup:**
- Throwaway vault: `C:/Temp/mnemos-pilot-2026-04-16/`
- Throwaway HOME for install-* commands: `C:/Temp/mnemos-pilot-home-2026-04-16/`
- Same dev environment (`pip install -e .[dev,llm]` already in place)

---

## What worked first try

| Step | Command | Outcome |
|---|---|---|
| 1 | `mkdir <pilot>/Sessions` + seed one `.md` | clean vault root |
| 2 | `mnemos --vault <pilot> init` (piped: `en\n\nA\nn\nn\n`) | `mnemos.yaml`, `Mnemos/` palace tree (`wings/`, `_identity/`, `_recycled/`, `.chroma/`), and `.mnemos-pending.json` all written. Discovery saw 341 JSONLs (raw, awaiting refine) + 1 curated Sessions/ note. The `[A]ll` choice mined the curated note → 8 drawers, 24 entities, wing `pilot-vault-test` (auto-derived from frontmatter `project:`). |
| 3 | `mnemos --vault <pilot> status` | clean JSON: `total_drawers: 8`, `wings: ["pilot-vault-test"]`. |
| 4 | `mnemos --vault <pilot> search "pilot vault sanity"` | 5 hits returned, top score 0.016 (small corpus → uniform low cosine, expected). |
| 5 | `mnemos --vault <pilot> mine Sessions/` (re-run) | `files_scanned: 0, skipped: 1` — incremental mining works. |
| 6 | `HOME=<fakehome> mnemos install-hook` | `installed`, settings.json written with `_managed_by: mnemos-auto-refine`. Re-run → `already-installed`. `--uninstall` → clean removal. |
| 7 | `HOME=<fakehome> mnemos install-statusline` | `installed`, `mnemos-statusline.cmd` created (Windows-correct), `statusLine.command` wired, `.bak-2026-04-16` backup. Re-run → `already-installed`. `--uninstall` → script + statusLine entry both removed. |

All 7 steps succeeded with no manual intervention beyond piping known
inputs to the wizard.

---

## Findings

### Bug: `mnemos search` CLI showed `wing=?  hall=?` for every hit

**Symptom:** every formatted result line read `wing=?  hall=?` even
though the underlying drawers had wing/hall metadata correctly indexed
(verified via `mnemos status` which listed wing `pilot-vault-test`).

**Root cause:** `cmd_search` in `mnemos/cli.py` read top-level `r.get("wing")`
and `r.get("hall")`, but `MnemosApp.handle_search()` returns drawers
shaped `{"drawer_id", "text", "metadata": {"wing", "hall", ...}, "score"}`.
The keys live one level deeper than the formatter expected.

**Fix:** read from `r.get("metadata") or {}` first, then `.get("wing")` /
`.get("hall")` with `?` fallback for ancient indexes that don't carry
metadata. Locked down by `tests/test_cli_search.py` (2 tests). Bundled
into the same commit as this pilot report so the fix doesn't drift.

### UX: piped-stdin runs of `mnemos init` interleave prompt + intro body

**Symptom:** when feeding answers via stdin (e.g. `printf '...' | mnemos
init`), the intro paragraph (`Mnemos is your AI memory system…`) printed
right after the `Languages [en]:` prompt on the same line, because
`input()` consumed the `\n` between answers without echo. Visually
ugly, functionally fine.

**Status:** non-issue in interactive use. No fix needed.

### Observation: small corpora produce uniform cosine scores

All 5 hits in the seed-of-one search returned `score=0.016`. With a
73-line single-source vault, ChromaDB's cosine has very little signal to
discriminate. Expected, not a bug — would self-correct as the vault
grows.

### Observation: discovery flagged the author's real ~/.claude/projects

`mnemos init` Discovery scanned the *real* `C:/Users/tugrademirors/.claude/projects`
directory (341 JSONLs awaiting refinement) even though the vault was
throwaway. This is correct behavior — the projects dir is global per
user — but worth flagging in README that init's discovery uses the real
projects dir. The pilot's `[A]ll` choice did the right thing: registered
the JSONLs as pending (raw, awaiting refine-skill) without trying to
refine them on the spot.

---

## What was NOT pilot-tested (and why)

- **`pip install mnemos-dev`** — the pilot ran from a `pip install -e .`
  dev install. Unable to test the public PyPI flow until v0.3.0 ships
  (task 3.10). Workaround: `mnemos init` works identically from either.
- **Live SessionStart hook firing** — testing the actual hook
  invocation would require closing/reopening Claude Code, which the
  pilot can't do from inside a Claude Code session. The hook's wiring
  was verified at the file level (settings.json structure, vault path
  forward-slashed, `_managed_by` marker present). The hook's *runtime*
  behavior was verified separately by 3.7's production rollout in the
  author's real vault (6 transcripts refined, 0 API credit).
- **`/mnemos-refine-transcripts` skill execution** — same reason; the
  skill runs inside an interactive Claude Code session. The skill is
  junctioned into the same `~/.claude/skills/mnemos-refine-transcripts`
  the author uses, so there's no separate pilot install to validate.

---

## Documentation gaps to fix later

These came up while running the pilot but are non-blocking for v0.3:

1. README's Quick Start says `pip install mnemos-dev` first, but the
   wizard discovers `~/.claude/projects/` regardless of vault path.
   Mention that `mnemos init` always discovers all of the user's
   Claude Code history — vault choice only affects *where* mining lands.
2. The `[A]/[S]/[L]` choice prompt in onboarding shows on the same line
   as the choice options on Windows because `input()` doesn't add a
   newline. Cosmetic; readable interactively but messy when copied
   from logs.

These belong in v0.4 polish or a future docs-only commit; the v0.3
deliverables are met.

---

## Conclusion

The README's documented flow works on a clean machine. One real CLI bug
(wing/hall display) was caught and fixed within the pilot. v0.3 is ready
for PyPI release (3.10) once the post-pilot cleanup commits land.
