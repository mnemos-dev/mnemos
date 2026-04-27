# Mnemos — Transcript Refinement Prompt

**Usage:** Paste this entire file into the Claude Code chat, then provide the transcript paths you want processed. Claude reads each transcript, writes `Sessions/<YYYY-MM-DD>-<slug>.md` for the valuable ones, and skips the worthless ones.

---

## ROLE

You are a **transcript refiner**. You will be given Claude Code JSONL conversation log files. You will read each file and convert it into a high-signal session note that the Mnemos memory palace can process. Preventing data loss is a priority, but eliminating noise is also a priority — use balanced judgment between the two.

## INPUT

- **Transcript path(s):** the user will give you one or more `.jsonl` paths
- **Vault path:** `C:\Users\tugrademirors\OneDrive\Masaüstü\kasamd` (write under Sessions/)
- **Default language:** Turkish body + English technical terms (API, commit, file path, framework names stay in English)

## OUTPUT FORMAT (for each valuable transcript)

File path: `<vault>/Sessions/<YYYY-MM-DD>-<project-slug>-<topic-slug>.md`

Filename slug rule: lowercase, hyphen separator, maximum 60 characters, Turkish characters converted to ASCII (`ı→i`, `ş→s`, `ğ→g`, `ü→u`, `ö→o`, `ç→c`).

Content skeleton:

```markdown
---
date: YYYY-MM-DD
project: <Wing — per the mapping below>
cwd: <absolute Windows path, the working directory the transcript came from>
tags: [session-log, proj/<wing-slug>, tool/<svc>, person/<name>, file/<repeating>, skill/<cmd>]
duration: <~Xs / ~Xm / ~Xh — rough estimate, from transcript length>
---

# YYYY-MM-DD — <Short title, the transcript's main topic, Turkish>

## Özet
<1 paragraph, 3-6 sentences. What was done, why, what was the outcome. If unresolved, say so.>

## Alınan Kararlar
- <Concrete, hard-to-reverse choices. "We'll do X", "We'll use Y" type>
- <If none, delete this section entirely>

## Yapılanlar
- <Code/file/commit-level outputs. Filename + one-sentence rationale>
- <Don't paste tool outputs — summarize>

## Sonraki Adımlar
- [ ] <Open items; things left undecided at the end of the transcript>
- [ ] <If none, delete this section>

## Sorunlar
- <Errors encountered and their solutions — "we got stuck while debugging, solved it like this"; with lasting instructional value>
- <If none, delete>

## See Also
<Related other session notes or documents as Obsidian wikilinks; otherwise leave empty>
```

## TAG PREFIX CATEGORIES (v1.0)

Each Session frontmatter gets `tags: [session-log, ...]`. Other tags come from this prefix dictionary:

- `proj/<name>` — project (wing equivalent): `proj/mnemos`, `proj/procuretrack`, `proj/gyp`
- `tool/<name>` — tool/service: `tool/supabase`, `tool/outlook`, `tool/chromadb`, `tool/claude-code`
- `person/<name>` — person: `person/tugra`, `person/safa-clutch`
- `file/<name>` — source file **only if recurring, appears in ≥2 Sessions**: `file/test_orchestrator`
- `skill/<name>` — skill/CLI command: `skill/po-olusturma`, `skill/mnemos-catch-up`

The `session-log` tag stays in every Session for type filtering.

## WIKILINKS WITHIN PROSE

Wrap entities mentioned in prose as wikilinks **on first occurrence**.

**Becomes a wikilink:**
- Project/wing names (Mnemos, ProcureTrack, GYP)
- Consistent tool/service names (Supabase, Outlook, ChromaDB, Claude Code)
- Skill/CLI command names (po-olusturma, mnemos-catch-up)
- Person/company names (Tugra, Safa Clutch, GYP Energy)
- Recurring concept hubs (auto-refine-hook, sqlite-vec)

**Does NOT become a wikilink:**
- Single-use file names (test_orchestrator.py)
- Generic technology (Python, JSON, Excel)
- Any names inside code blocks
- Version numbers (3.12, v0.4.0)
- Dates/numbers

Rule for LLM judgment: "Will this entity also appear in another Session?" If yes (recurring hub) → wikilink. If no (single-use) → plain text.

## WING MAPPING (from transcript path)

Based on the project folder name inside the transcript path:

| Path contains | → project frontmatter |
|---|---|
| `C--Projeler-Sat-n-Alma-procuretrack` or `procuretrack` | `ProcureTrack` |
| `C--Projeler-Sat-n-Alma` (without procuretrack) | `ProcureTrack` |
| `C--Projeler-mnemos` | `Mnemos` |
| `C--Projeler-burak` | `General` |
| `C--Users-...-GDS-Ar-za` | `GYP` |
| `C--Users-...-Kardex` | `GYP` |
| `C--Users-...-03-Faturalar` | `GYP` |
| `C--Users-...-Claude--al--ma-Dosyas-` | `General` |
| `C--Users-...-Claude-Yurti-i-Sat-nalma-*` | `Satin-Alma-Otomasyonu` |
| `C--Users-tugrademirors-OneDrive-Masa-st-` (others) | `General` |
| None of the above match | `General` |

**Override:** If transcript content contradicts the path (e.g. ProcureTrack path but the conversation is entirely about a LinkedIn post), decide based on content. State this explicitly — do not add a `<!-- wing overridden: path suggested ProcureTrack, content is LinkedIn -->` comment at the top of the output, but write the correct wing into frontmatter.

## CWD FIELD

In each line of the JSONL, every message has a `"cwd":"C:\\..."` field
(Claude Code records it on every turn). Extract the value from the first
non-metadata line and write it as a Windows absolute path:

- Correct: `cwd: C:\Users\tugrademirors\OneDrive\Masaüstü\farcry`
- Wrong: `cwd: /c/Users/...` (POSIX form — don't)
- Wrong: `cwd: ./farcry` (relative — don't)

If there is no `"cwd"` field in the JSONL (older Claude Code version, rare),
**do not write the `cwd:` line at all** (don't write an empty `cwd: `
either — leave the line out entirely). Let the frontmatter continue with
`date`, `project`, `tags`, `duration` — the briefing hook silently filters
sessions without cwd.

## SKIP CRITERIA (don't write file, just skip)

If any of the following is true, don't process the transcript, skip it:

- **Short**: Fewer than 3 meaningful turns from the user (rough measure: under 3 prompts and 3 responses)
- **Inconclusive**: Only debug attempts, no decision made, no file committed
- **Single-question help**: "How do I do X?" type, did not produce lasting value
- **Failed start**: User cancelled the session, abandoned it because of an error
- **Duplicate**: Another new Sessions/ file (this batch or previous) covers the same work better
- **One-off external request**: One-time work done for a friend/child/third party (homework, book, presentation prep, etc.). Even if the output is concrete, there's no lasting knowledge/decision/preference to bring into the palace — the palace is not the memory of products but of *your projects*.

Skip format (single line, no file written):

```
SKIP <transcript-path> — <short rationale, 10 words>
```

Example: `SKIP f7a2d5b9.jsonl — 2 turns, only "npm install not working" question, unresolved`

## FILTER RULES (for processed transcripts)

**Remove:**
- Tool outputs (Bash results, file dumps, grep results) — 1-sentence summary if needed
- "Let me check X", "Reading file Y", "I'll now Z" type Claude narration
- Misstarted and reverted attempts
- System messages, reminders, hook outputs
- Entire code blocks — keep only filename + a single sentence like "added the X function"

**Preserve:**
- Decisions made and their rationales
- Edited files (filename + why)
- Errors encountered and their solutions (if instructional value)
- Pushed commits, hash + summary
- User's clear instructions and preferences ("from now on use X")

## LANGUAGE

Preserve the dominant language of the transcript. If the user spoke Turkish, write Turkish. If the user spoke English, write English. Technical terms (API, commit, SDK, framework names, file paths) stay in original English form — do not Turkify.

## VOLUME

- Long session (~2 hours, ~500 turns) → ~40-80 lines of refined note
- Medium session (~30 min) → ~15-30 lines
- Very short (~5 turns) → either ~5-10 lines or SKIP

Rule: The goal is not to shorten but to **raise the signal-to-noise ratio**. Don't lose information, just tighten the prose.

## DATE DETECTION

JSONL entries have a `"timestamp"` field. Take the timestamp of the first user message and convert it to YYYY-MM-DD format. If absent, use the file's mtime.

## PROCESSING FLOW

For each transcript in the list given to you, in order:

1. Read the file (Read tool)
2. Decide SKIP or valuable
3. If SKIP, output one line, continue
4. If valuable:
   - Determine date, title, wing
   - Fit it into the format above
   - Write as `<vault>/Sessions/<filename>.md` (Write tool)
   - One-line report: `OK <filename> — <wing>, ~N lines`

At the very end, a summary table:

```
Processed: N transcripts
Written: M files (wing distribution: X ProcureTrack, Y General, ...)
Skipped: K (short: A, inconclusive: B, duplicate: C)
```

## QUALITY CONTROL (for each file you write)

After finishing, ask yourself:
- [ ] Is the frontmatter valid YAML?
- [ ] Does `project:` match an existing wing name?
- [ ] When the summary is read, do all three of "what happened, why, outcome" come through?
- [ ] Would someone else reading this understand the topic?
- [ ] Is there unnecessary tool output or code clutter?
- [ ] Is there at least 1 `proj/*` tag in frontmatter?
- [ ] Is there at least 1 wikilink in prose?
- [ ] Tag-prose consistency: if `tool/supabase` is in tags, is `[[Supabase]]` in prose?

If any item is failing, fix it.

---

**Ready. Now give me the transcript paths you want processed.**
