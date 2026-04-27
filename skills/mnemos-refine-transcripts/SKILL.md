---
name: mnemos-refine-transcripts
description: >
  Refines Claude Code JSONL transcripts (~/.claude/projects/) into
  high-signal Sessions/<YYYY-MM-DD>-<slug>.md notes in the Mnemos vault.
  Triggers: "/mnemos-refine-transcripts", "refine transcripts",
  "summarize JSONLs and write to Sessions", "process raw logs",
  "import Claude Code history to vault", "process unprocessed transcripts".
  Does NOT call the mnemos API, does NOT call any LLM API — work is done by Claude in this session.
---

<!--
INSTALL NOTE (mnemos-dev ≥ v0.3):
This skill uses machine-specific paths. Setup:

1. Copy this folder under ~/.claude/skills/mnemos-refine-transcripts/
   (or symlink/junction it — repo is canonical, the junction must not drift).
2. Edit the paths in the "Constants" section below for your own system:
   - mnemos installation path (canonical prompt + extractor are read from here)
   - Claude Code transcripts root folder (~/.claude/projects/)
   - Obsidian vault Sessions/ path
   - Ledger path (skill state)

In v0.3 the `mnemos init` wizard resolves most of these paths;
manual edits may still be needed for some non-standard setups.
Use `mnemos install-hook` for automatic hook installation.
-->

# Mnemos — Refine Transcripts

JSONL transcript → refined `Sessions/*.md` conversion. The rules are kept in
a single source; this skill only provides the **discovery + ledger + write**
mechanics.

## Constants

- **Canonical refinement prompt:** `C:\Projeler\mnemos\docs\prompts\refine-transcripts.md`
  (output format, wing mapping, SKIP criteria, filter rules — all here)
- **Prose extractor:** `C:\Projeler\mnemos\scripts\extract_jsonl_prose.py`
- **Transcript root:** `C:\Users\tugrademirors\.claude\projects\`
- **Vault Sessions:** `C:\Users\tugrademirors\OneDrive\Masaüstü\kasamd\Sessions\`
- **Ledger:** `C:\Users\tugrademirors\.claude\skills\mnemos-refine-transcripts\state\processed.tsv`

## Trigger examples

- `/mnemos-refine-transcripts` — unprocessed scan, pilot mode
- `/mnemos-refine-transcripts <path.jsonl>` — single file
- `/mnemos-refine-transcripts <dir>` — all JSONLs under dir
- `/mnemos-refine-transcripts --limit 5` — pilot batch
- `/mnemos-refine-transcripts --all` — all unprocessed, no questions asked
- `/mnemos-refine-transcripts --include-subagents` — also include subagent JSONLs (default: excluded)

## Flow

### 1) Load the canonical prompt

First task on every run: Read `C:\Projeler\mnemos\docs\prompts\refine-transcripts.md`
with the Read tool. The rules come from there — this SKILL.md does not
restate the rules.

If the file is missing, tell the user and stop: "Canonical refinement prompt
not found. The mnemos repo path probably changed — update me."

### 2) Build the transcript list

Based on the argument:

| Input | Behavior |
|---|---|
| `<path.jsonl>` | Single file |
| `<dir>` (folder) | Glob `<dir>/**/*.jsonl` |
| no args / `--unprocessed` | Glob `~/.claude/projects/**/*.jsonl`, filter by ledger |
| `--limit N` | First N |
| `--all` | All unprocessed, skip pilot |

**Ledger filter:** Read the `state/processed.tsv` file with the Read tool.
Each line is in `<abs-path>\t<OK|SKIP>\t<meta>` format. If a path in the
first column is in the list, do not process it again on this call.

If the file is missing, no work has been done yet — the filter is the empty set.

**Subagent filter (default ON):** Skip JSONLs whose path contains `/subagents/`
or `\subagents\` — these are transcripts of subtasks of the parent session,
not conversations with the user, and rarely have lasting value. Use the
`--include-subagents` flag to bring them back.

### 3) Pilot protocol

If NOT `--all` and the filtered list > 5:

1. Process the first 5 (steps 4-5)
2. Show interim summary:
   ```
   Pilot 5/N done. Wing distribution: X Mnemos, Y ProcureTrack, ...
   SKIP rate: K/5
   Example written file: <first OK filename>
   ```
3. Ask: "Should I continue? (`yes` / a number `N` to limit / `stop`)"
4. Continue/finish based on the answer

If invoked with a single file, dir, or `--limit N`, no pilot — process directly.

### 4) For each transcript

```bash
PYTHONUTF8=1 python "C:/Projeler/mnemos/scripts/extract_jsonl_prose.py" "<abs-path>"
```

Stdout is the digest. **Fast-path:** If you see `User turns detected: 0`
in the digest header, there is no need to evaluate the canonical prompt —
auto SKIP ("empty transcript, 0 user turns"), write to the ledger, move
on to the next file.

Otherwise, evaluate the digest against the canonical prompt's rules:

- **If SKIP** (criteria from the prompt):
  - One-line report: `SKIP <basename> — <short reason>`
  - Write to ledger: `<abs-path>\tSKIP\t<reason>`
  - DO NOT write a file
- **If valuable:**
  - File path: `<vault>/Sessions/<YYYY-MM-DD>-<slug>.md`
  - Slug rule as in the prompt file (lowercase, hyphens, Turkish→ASCII, max 60)
  - **Collision check:** If the same slug+date exists, append `-2`, `-3`
  - Write with the Write tool
  - One-line report: `OK <filename> — <wing>, ~N lines`
  - Write to ledger: `<abs-path>\tOK\t<filename>`

### 5) Ledger append

Append to the ledger after each file. Create the file if missing. Format:
```
<abs-path>\t<OK|SKIP>\t<filename-or-reason>
```

No header. Tab-separated. UTF-8.

**Important:** Update the ledger after each transcript, not at the end of
the batch — for resume in case the session is interrupted.

### 6) Final summary

Format from the prompt:
```
Processed: N transcripts
Written: M files (wing distribution: X Mnemos, Y ProcureTrack, ...)
Skipped: K (short: A, inconclusive: B, duplicate: C, ...)
Ledger: <tsv-path>
```

## v1.0 Tag/Wikilink Hybrid Rules

For each Session, we generate a 5-prefix tag category in the frontmatter
and entity wikilinks in the prose. Detailed rules are in
`docs/prompts/refine-transcripts.md`:
- TAG PREFIX CATEGORIES
- WIKILINKS IN PROSE
- QUALITY CONTROL checklist

Use these three sections as a live reference during refinement.

## Critical principles

- **NO mnemos API calls.** Refinement = preprocess done in the Claude Code
  session. The output is only file writes. (If the user separately runs
  `mnemos mine`, the written Sessions/ files go into the vault.)
- **NO LLM API calls.** Everything is Claude in this session.
- **Single canonical prompt source:** `mnemos/docs/prompts/refine-transcripts.md`.
  Rule changes are made there, not here.
- **Ledger is persistent.** Unless `state/processed.tsv` is deleted, the same
  JSONL will not be processed again.
- **Skips are also recorded.** So nothing is judged "no value" twice.

## File structure

```
~/.claude/skills/mnemos-refine-transcripts/
├── SKILL.md          ← This file
└── state/
    └── processed.tsv ← Ledger (persistent across sessions)
```

## Troubleshooting

- **Extractor Unicode error** → The `PYTHONUTF8=1` prefix may have been omitted
- **Path contains a space** → Wrap it in quotes in the Bash call
- **Slug leaked Turkish characters** → Reapply the ASCII table from the prompt file
- **Ledger corrupted / want to start over** → Delete `processed.tsv`, recall
