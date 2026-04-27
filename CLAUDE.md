# Mnemos — Claude Code Project Instructions

This file is auto-loaded by Claude Code whenever it operates under
`C:\Projeler\mnemos`. Project-specific rules only; global rules live at
`~/.claude/CLAUDE.md`.

---

## One-word resume protocol 🧠

**Triggers:** when the user types one of the following after `/clear`:
- Standalone `mnemos`
- `devam`, `kaldığımız yer`, `resume`, `nerede kalmıştık` (Turkish triggers
  preserved — the user is Turkish-speaking)
- `mnemos'a devam`, `mnemos dev`

**Don't implement anything yet — load the context first.** Flow:

1. Read `STATUS.md` — project purpose + current capability set
2. Read `docs/ROADMAP.md` — find the active version (🔄) and the first
   unchecked `[ ]` or in-progress `[~]` task
3. Run `git log --oneline -10` + `git status --short` — recent commits and
   dirty files
4. **Give a <100-word summary:**
   - Project purpose (one sentence, from STATUS §1)
   - Current version + phase (e.g., "v0.4 AI Boost in-progress")
   - Last completed task + commit hash
   - Next pending task (first `[ ]` or `[~]`)
   - Flag dirty / uncommitted state if present
5. **Ask:** "Continue, or different work?" — don't start implementing without
   user confirmation.

**Note:** if the user names a task directly (e.g., "let's do 3.3"), still run
steps 1–4 quickly but skip the question and go straight to that task.

---

## Project snapshot

- **What:** Obsidian-native AI memory palace. Turns Claude Code JSONL
  transcript history into searchable markdown memory.
- **Canonical plan:** `docs/ROADMAP.md` — single source of truth
- **External status:** `STATUS.md` — what the project does and where it's
  heading, written for someone who just downloaded it
- **Skill:** `skills/mnemos-refine-transcripts/` — junctioned into
  `~/.claude/skills/`; this repo is canonical
- **Canonical refinement prompt:** `docs/prompts/refine-transcripts.md`
- **Author's vault (for testing/pilots):**
  `C:\Users\tugrademirors\OneDrive\Masaüstü\kasamd`
- **PyPI:** `mnemos-dev` — stable v0.3.3, v0.4.0 (AI Boost / Phase 1) in
  preparation
- **GitHub:** `github.com/mnemos-dev/mnemos`

---

## Working discipline

1. Before starting a task, flip the ROADMAP checkbox `[ ] → [~]` (in
   progress)
2. When the task is done, **in a single commit:**
   - ROADMAP checkbox `[~] → [x]` + commit hash + date
   - Add the relevant capability to STATUS.md §2 "What works today"
     (often by moving an item up from §3 to §2)
   - Code + tests
3. After any skill / script / docs change, automatic `git add → commit →
   push` (global rule)
4. If scope changes, update the ROADMAP line; split into sub-tasks if
   needed
5. When starting a new phase, write a design spec under `docs/specs/`
   first (Phase 0 format); implementation follows
6. **Session-end STATUS discipline** — ROADMAP-tracked work already keeps
   STATUS current via rule 2. But two situations are lost on the next
   resume unless STATUS is manually updated:
   - **Off-ROADMAP meta work** (repo polish, CI workflow, README ELI5,
     social preview, docs refresh — work without a checkbox): add a
     `### Post-v0.x.y repo polish (YYYY-MM-DD, not a release)` block to
     STATUS. Update the "Next session starts here" block too if needed,
     so meta work doesn't shadow the next Phase.
   - **Pending user action** (GitHub UI upload, manual command, external
     token rotate — work that leaves no trace in code/git): add a line
     marked `🟡 **Pending user action**` to STATUS. The marker is
     mandatory — the resume protocol grep's for this glyph.
   - At the same time, trim any stale STATUS sections (old stats,
     hardening recap that no longer applies).
   - **Trigger:** phrases like "that's it", "I'm closing", "let's end the
     session", "prep for new session", "before /clear" all warrant this
     checkpoint. Even without a prompt, after a batch commit ask
     yourself: "does this work need a STATUS trace?"

---

## Architectural reminders

- **Obsidian is master; ChromaDB/sqlite-vec is index.** No memory exists
  outside the vault. To delete, move the `.md` file to `_recycled/` — the
  watcher cleans the index.
- **Mnemos does not call an LLM.** If the user passes the `--llm` flag,
  the Claude API is used; otherwise everything is regex + heuristics. The
  refinement skill also runs **inside the Claude Code session** —
  zero cost.
- **Dual collection:** `mnemos_raw` (verbatim, lossless) + `mnemos_mined`
  (fragments). Search merges them via RRF. Raw = baseline, mined =
  precision.
- **Phase axes:** Phase 0 = API-free foundation (delivered). Phase 1 =
  AI boost. Phase 2 = automation. Aligned with v0.x versions in the
  ROADMAP.

---

## Forbidden / careful zones

- Don't pollute the production environment with bare `pip install` — for
  dev use `pip install -e ".[dev,llm]"`
- `mnemos mine --rebuild` can cause data loss on a large vault; the
  atomic-rebuild implementation in Phase 0 is in place, but always work
  with `git status` + a ChromaDB backup
- ChromaDB `mnemos/.chroma/` and SQLite `mnemos/graph.json` are local
  runtime data — gitignored, do not commit
- Benchmark data under `benchmarks/longmemeval/data/` is large —
  gitignored
- Junction (`~/.claude/skills/mnemos-refine-transcripts`) ↔ repo: must
  not drift. Skill updates go to the repo's `SKILL.md` only; the junction
  reflects the same file.

---

## Short command glossary

| Command | What it does |
|---|---|
| `pytest tests/ -v` | All tests |
| `python -m mnemos --vault <path>` | Start the MCP server manually |
| `mnemos benchmark longmemeval --limit 10` | Quick benchmark smoke |
| `mnemos mine Sessions/ --rebuild` | Reindex the vault from scratch (atomic) |
| `git push origin main` | Reflex after any skill/docs/script commit |
