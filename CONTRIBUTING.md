# Contributing to Mnemos

Thanks for taking the time to look at the internals. Mnemos is a small
codebase with a tight focus — this guide explains the conventions so you
can land changes that fit.

If anything here is unclear, file an issue at
[github.com/mnemos-dev/mnemos/issues](https://github.com/mnemos-dev/mnemos/issues).

---

## Quick start (dev environment)

```bash
git clone https://github.com/mnemos-dev/mnemos.git
cd mnemos
python -m venv .venv
.venv/Scripts/activate            # Windows
# source .venv/bin/activate       # macOS / Linux

pip install -e ".[dev,llm]"
pytest tests/ -q
```

`pip install -e` puts the `mnemos` CLI on your PATH while pointing it at
your working tree. Edit, re-run, no rebuild.

For benchmark work add `[benchmark]` and download the LongMemEval data
under `benchmarks/longmemeval/data/` (gitignored).

---

## Project layout

| Path | What's inside |
|---|---|
| `mnemos/` | Library + CLI + MCP server. Public surface is small. |
| `tests/` | Pytest suite, ~250 tests. New code → new tests, no exceptions. |
| `skills/mnemos-refine-transcripts/` | Claude Code skill, junctioned into `~/.claude/skills/`. |
| `docs/ROADMAP.md` | **Single source of truth** for what's planned, in-progress, or shipped. |
| `docs/specs/` | Per-phase design docs (Phase 0 in archive, Phase 1+ as they land). |
| `docs/prompts/refine-transcripts.md` | Canonical refinement prompt — the skill loads this, never duplicates it. |
| `docs/archive/` | Delivered design + plan artifacts. Read for rationale, not for current behavior. |
| `STATUS.md` | External-facing snapshot: what works today vs. what's coming. |

---

## Workflow discipline

1. **Pick a task from `docs/ROADMAP.md`.** Look for the active version
   (🔄) and the first unchecked `[ ]` or in-progress `[~]` item.

2. **Flip the checkbox `[ ] → [~]`** before you start coding. This
   marks the task as in-progress so two people don't duplicate work.

3. **One feature → one commit.** That commit must include:
   - The code change itself
   - Tests that cover the new behavior
   - A `STATUS.md` update if the task added a user-visible capability
   - The ROADMAP checkbox flipped to `[x]` *(commit hash backfilled in a
     small follow-up commit — see existing history)*

4. **Push immediately after committing** when the change touches skills,
   scripts, or docs. Skill updates that sit unpushed cause drift between
   the repo and the junctioned `~/.claude/skills/mnemos-refine-transcripts`
   that everyone else sees.

5. **Scope changed mid-task?** Update the ROADMAP entry. If the task
   needs splitting, replace `3.4` with `3.4a` + `3.4b` and re-check the
   sub-items.

---

## Commit message style

Look at recent history for the pattern:

```
feat: <short summary> (v0.X task N.M)
fix: <what broke and how>
docs: <what doc changed>
perf: <measurable improvement>
test: <coverage addition>
```

Body (optional): a few short paragraphs on the *why* and on any non-obvious
trade-offs. Co-author trailer for AI assistance is welcome.

---

## Coding conventions

- **Python 3.10+.** All modules start with
  `from __future__ import annotations`.
- **Dataclasses over dicts** for any record with more than two fields.
- **Type hints everywhere.** Tests get them too.
- **Pure functions in domain modules** (`onboarding.py`, `pending.py`,
  `room_detector.py`, …). Side-effects (CLI prompts, ChromaDB writes)
  live in `cli.py` and `server.py`.
- **No silent fallbacks.** If a config value is wrong, raise. If a status
  value is unknown, raise. Errors should fail fast at the boundary, not
  cascade as `None` through three call sites.
- **No premature abstraction.** Three similar lines is better than a
  framework. Add the abstraction when the fourth use case arrives.
- **Tests are organized by class**, one class per behavior cluster, with
  a docstring header naming the test (see `tests/test_pending.py` for
  the pattern).

---

## Adding a new language for mining markers

Markers live in `mnemos/patterns/`:

```
mnemos/patterns/
  en.yaml       # 87 markers across 4 halls
  tr.yaml       # 85 markers across 4 halls
```

To add (say) German:

1. Copy `en.yaml` to `de.yaml`.
2. Translate each marker. Keep the same hall structure (`decisions`,
   `preferences`, `problems`, `events`).
3. Aim for ~80 markers — quality beats quantity. Markers should match
   real-world phrasing in that language.
4. Add `"de"` to the `languages` list in your test vault and run
   `mnemos mine` against a small German corpus to sanity-check
   precision.
5. Add a test in `tests/test_miner.py` exercising at least one marker
   per hall.

---

## Working on the refinement skill

### SessionStart auto-refine hook

`mnemos install-hook` (invoked by `mnemos init`, or manually) adds a
`SessionStart` entry to `~/.claude/settings.json`. The hook points at
`scripts/auto_refine_hook.py`, a synchronous wrapper that:

1. Reads `.mnemos-pending.json` and `~/.claude/skills/mnemos-refine-transcripts/state/processed.tsv`.
2. Picks the last 3 unprocessed JSONLs (excluding subagent logs under
   `/subagents/`) and computes the total backlog.
3. Writes `<vault>/.mnemos-hook-status.json` for statusline consumption.
4. Emits SessionStart `additionalContext` JSON if the weekly backlog
   reminder is due.
5. Spawns a detached `python -m mnemos.auto_refine_background` worker,
   then exits 0 in <1 second.

The background worker acquires a `filelock` on `<vault>/.mnemos-hook.lock`
to prevent concurrent sessions from duplicating work. It runs
`claude --print --dangerously-skip-permissions "/mnemos-refine-transcripts <path>"`
for each picked JSONL (no LLM API cost — uses the user's own Claude Code
quota), then `python -m mnemos.cli --vault <vault> mine <vault>/Sessions`.

See `docs/specs/2026-04-15-v0.3-task-3.7-auto-refine-hook-design.md` for
the full architecture rationale, UX channels, failure modes, and acceptance
criteria.

#### Legacy hooks early adopters may still have

Some early users wired one or both of these directly into `~/.claude/`
before the auto-refine hook existed. They are obsolete; user-facing
removal steps are in the README's *Migrating from older session-memory
setups* section. Don't reintroduce equivalents in the repo:

- `~/.claude/skills/session-memory/` — manual SAVE-on-keyword skill
  (Turkish triggers: `kaydet`, `bye`, `görüşürüz`, …). The auto-refine
  hook captures the same content unconditionally.
- `~/.claude/hooks/mnemos-session-mine.py` + `mnemos-mine-worker.py` —
  raw-transcript miner that ran every SessionStart with its own lock
  file. Refining-before-mining removes 99% of tool noise; running both
  pipelines on the same vault wastes CPU and competes for the lock.

---



The skill at `skills/mnemos-refine-transcripts/` is junctioned into
`~/.claude/skills/`. **The repo is canonical** — only edit
`SKILL.md` here, never the linked copy.

The canonical extraction rules live in `docs/prompts/refine-transcripts.md`.
The skill loads this prompt at runtime; do not duplicate the rules into
`SKILL.md`. When you change the prompt, both stay in sync automatically.

Skill changes do not need a Python test, but the smoke test is:

```bash
# In a Claude Code session:
/mnemos-refine-transcripts --limit 3
# Inspect the new files in <vault>/Sessions/. Sanity check signal vs noise.
```

---

## Architectural lines you should not cross

These constraints exist for real reasons. If a change requires crossing
one, raise it in an issue first:

- **Obsidian is the source of truth.** Every memory is an `.md` file
  the user can read, edit, or delete by hand. ChromaDB / sqlite-vec are
  rebuildable indexes, not storage.
- **Mnemos itself never calls an LLM API.** When the user passes
  `--llm` we use the Anthropic SDK; otherwise everything is regex +
  heuristic. The refinement skill runs *inside* the user's Claude Code
  session, on their existing quota — not via Anthropic SDK.
- **Dual collection separation.** `mnemos_raw` (verbatim, lossless) and
  `mnemos_mined` (fragments) are searched independently and merged via
  RRF. Don't mix the two at write time.
- **Junction / symlink drift is forbidden.** The repo and the linked
  skill copy must never diverge. If your change touches the skill,
  edit the repo file and let the junction reflect it automatically.
- **The backend count stays at two.** ChromaDB and sqlite-vec share a
  thin `SearchBackend` abstract. A 2026-04-17 parity benchmark proved
  they produce identical recall, so the user-facing question is
  reliability / environment fit, not quality. PRs that add a third
  backend (Qdrant, LanceDB, pgvector, …) will be held to a very high
  bar: concrete gap the existing two don't cover, maintenance commitment,
  and full feature parity with `mnemos migrate`. Most of the time the
  right answer is improving one of the two we have.

---

## Reporting bugs

Open an issue with:

- Mnemos version (`pip show mnemos-dev`)
- Python version + OS
- The command you ran + full traceback
- Vault layout if relevant (sanitize paths)

For mining quality issues, attach a small `.md` file that reproduces the
miss. We treat false negatives (missed memories) as more serious than
false positives.

---

## Architectural rule (v1.1): No Anthropic API calls

**Never** import `anthropic` or call `Anthropic().messages.create()` in
`mnemos/` or `skills/`. All LLM operations must invoke skills via
`claude --print --dangerously-skip-permissions --model sonnet "/<skill> <args>"`.
The intent is that Mnemos costs the user nothing beyond their existing
Claude Code subscription quota — no API spend, no surprise bills.

CI enforces this via grep:

```bash
! grep -rn "anthropic\.Anthropic\|from anthropic" mnemos/ skills/ \
    --include="*.py" --include="*.md" \
    | grep -v "# noqa: no-api"
```

The `_child_env()` helper in `recall_briefing.py` and `session_end_hook.py`
strips `ANTHROPIC_API_KEY` from subprocess env so even an inherited key
cannot accidentally be used by a `claude --print` child.

If you have a genuine need to call the Anthropic API directly (out-of-band
benchmark scripts, research tools), document the rationale in the PR
description and add a `# noqa: no-api` comment to bypass the grep.

---

## License

By contributing you agree your code is released under the project's MIT
license.
