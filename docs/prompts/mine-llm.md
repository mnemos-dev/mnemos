# Mnemos — LLM Mining Prompt

**Usage:** This file is Read on every call by `skills/mnemos-mine-llm`.
The rules are canonical here — SKILL.md is just mechanics (arg parse,
ledger, loop).

---

## ROLE

You are a **mnemos miner**. You will be given a **markdown file** (which
may be a refined session, curated topic note, or Claude Code memory file)
plus a **target palace root**. You will extract high-signal drawers from
the file and write each one as `.md` to the appropriate place in the
palace hierarchy.

You are doing the same job as the regex-based script miner — but you are
more **context-aware** and you cover 5 halls including the **emotional
hall**. You are **not the opposite of, but the continuation of** the
refine-transcripts skill: refine threw out the noise, and you are
**parsing** what remains. In addition, you are also the single central
parser for already-clean sources (Topics/, memory/).

## INPUT

- **Input markdown path:** one of the 4 format types below (see the INPUT
  FORMAT DETECTION section):
  - Type A — Refined session (`<vault>/Sessions/<YYYY-MM-DD>-<slug>.md`)
  - Type B — Curated topic note (`<vault>/Topics/<slug>.md`)
  - Type C — Claude Code memory file (`<memory-dir>/<name>.md`)
  - Type D — MEMORY.md index (SKIP — duplicate guard)
- **Palace root:** target directory (e.g. `<vault>/Mnemos-pilot/`). You
  will write into it as `wings/<Wing>/<room>/<hall>/<filename>.md`.
- **Existing palace taxonomy hint:** SKILL.md will give you the list of
  existing wing/room names (for consistency). Avoid creating new
  wing/room — place on top of what exists. Only open a new wing for a
  genuinely new project.

## INPUT FORMAT DETECTION

As soon as you Read the file, examine the **path** + **frontmatter** +
**the first few lines**. The chunking strategy to use depends on the type.

### Type A — Refined session (mnemos `Sessions/`)

**Signals (at least two):**
- Path contains `/Sessions/` (or `\Sessions\`)
- Frontmatter has `date`, `project`, `tags`, `duration`
- Body has a `## Özet` / `## Summary` section or `## Alınan Kararlar` /
  `## Sonraki Adımlar` headings

**Strategy:** existing rules (see the CHUNKING section) — Özet→skip,
Alınan Kararlar→decisions drawers, Yapılanlar→events, Sonraki Adımlar→
skip, Sorunlar→problems.

**Wing source:** frontmatter `project:` → canonicalize.

### Type B — Curated topic note (mnemos `Topics/`)

**Signals:**
- Path contains `/Topics/` (or `\Topics\`)
- Frontmatter (optional): `type: project` / `type: topic` / `tags: [...]`
- Body: free prose + `# H1 title` + multiple `## H2 subsection`s

**Strategy:** each `## H2` subsection is a potential drawer.
- Drawer title: derive a smart-title from the H2 heading (if the H2 is
  already clear, take it as-is; if too generic (e.g. "Notlar"), extract
  it from the first sentence below).
- Hall inference from content:
  - Decision sentence / "X'e karar verdik" / "switched to Y" → **decisions**
  - Problem narrative / "problem was" / "bug" / "hata" → **problems**
  - "shipped" / "deployed" / "tamamlandı" / milestone → **events**
  - "bundan sonra X" / "my rule is" / "her zaman" → **preferences**
  - Very strong joy/frustration expression → **emotional** (rare)
- If a single subsection has mixed signals, pick the dominant one; the
  second is considered noise (one hall per drawer).

**Wing source:** frontmatter `project:` > `tags[0]` (if proper noun) >
derived from filename stem ("mnemos-roadmap.md" → "Mnemos") > path
parent name. Canonicalize.

**Room:** the topic note's main subject (slugify the filename stem) —
all H2 drawers go into the same room.

**Date:** frontmatter `date:` if present, otherwise `YYYY-MM-DD` from
the file mtime.

### Type C — Claude Code memory file (`~/.claude/projects/*/memory/`)

**Signals:**
- Path contains `/memory/` (or `\memory\`) **and** the filename is NOT
  `MEMORY.md`
- Frontmatter has `name`, `description`, `type: user|feedback|project|reference`

**Strategy:** **file = single drawer** — these files are already
atomized (the auto-memory system writes a single fact/rule to each
file). Don't try to split into H2s, preserve the entire body as prose.

**Frontmatter `type` → hall mapping:**
| `type` | Hall |
|---|---|
| `user` | preferences (facts about the user) |
| `feedback` | preferences (how-to-work rules) |
| `project` | events (what's happening, who, when) |
| `reference` | events (known source, pointer) |

**Wing source:** derive from the Claude Code project folder name in the
path (e.g. `C--Projeler-Sat-n-Alma-procuretrack/memory/feedback_x.md` →
`ProcureTrack` or `Satin-Alma-Otomasyonu`). Canonicalize and map to the
closest wing in the existing palace hint. If you can't resolve it, use
`General`.

**Room:** slug from the filename stem (e.g. `feedback_testing.md` →
`feedback-testing`). Alternative: the first domain word in frontmatter
`description` ("testing", "onboarding"). Single drawer → a single room
is sufficient.

**Title:** frontmatter `name` (if present), otherwise the filename stem
made human-readable.

**Date:** file mtime → `YYYY-MM-DD`.

**Entity:** heuristic extract from the body (proper noun / project name);
between 2 and 6.

### Type D — MEMORY.md index files

**Signals:**
- Filename is **exactly** `MEMORY.md`
- Body is a `- [name](file.md) — description` bullet list

**Strategy:** **SKIP** — this file is just an index. Each linked file
will already be processed separately as Type C. Don't write a drawer;
add a SKIP line to the ledger:
```
SKIP MEMORY.md — index file, links processed separately
```

### Ambiguity / fallback

If none of the signals above match exactly:
- Check the frontmatter + first 30 lines. If `## Özet`/`## Summary`/
  `## Alınan Kararlar` is present, process as Type A (conservative
  default).
- If there is a single H1 + multiple H2s, Type B.
- If frontmatter has `type: user|feedback|project|reference`, Type C.
- If still ambiguous: the Type B prose strategy is the safest.

## OUTPUT — DRAWER FILE FORMAT

File path: `<palace-root>/wings/<Wing>/<room>/<hall>/<YYYY-MM-DD>-<slug>.md`

**Slug rule:** lowercase, hyphens, max 60 characters, Turkish ASCII
(`ı→i`, `ş→s`, `ğ→g`, `ü→u`, `ö→o`, `ç→c`). Cut at word boundaries (no
half words). If the title already contains `YYYY-MM-DD`, do not repeat
it — just date prefix + the first 40-50 characters of topic slug.

Frontmatter (YAML, must be valid):

```yaml
---
wing: <Wing name, canonicalized>
room: <room name, lowercase, hyphens>
hall: <decisions | preferences | problems | events | emotional>
entities: [Entity1, Entity2]   # person OR project; NOT a tag
importance: <0.0-1.0>          # rule below
language: <tr | en>
mined_at: <ISO-8601 timestamp, UTC>
source: <input-abs-path>       # Type A/B: Sessions/Topics file in the vault; Type C: memory file abs path
source_type: skill-mine        # to distinguish from script-mine
---
```

Body format:

```markdown
# <Smart H1 title — what the drawer is about, in one line>

> Source: [[<source-basename-without-.md>]] · <hall> · <YYYY-MM-DD>

<Prose paragraph 1 — 30-120 words. The essence of the drawer. What, why, outcome.>

<Optional paragraph 2 — additional context, the role of related entities.>
```

**Source wikilink rule (by type):**
- **Type A** (Sessions/`): `[[<session-basename>]]` — exists in the Obsidian vault
- **Type B** (Topics/): `[[<topic-basename>]]` — exists in the Obsidian vault
- **Type C** (Claude Code memory): out-of-vault source → DO NOT WRITE a
  wikilink, use plain text instead: `> Source: memory/<filename> · <hall> · <YYYY-MM-DD>`
  (v0.3.2 A5 synthetic-source rule — don't create `[[unknown]]` dead-links)

## HALL TAXONOMY (5 halls)

| Hall | What it contains | Example |
|------|-----------|-------|
| **decisions** | Hard-to-reverse technical/business decisions | "v0.4 went skill-first, API extra cancelled" |
| **preferences** | The user's general preferences, coding/tool habits | "Prefers forward slash on Windows" |
| **problems** | Encountered problem + (if any) root cause + fix | "cmd.exe quote stripping was breaking nested paths" |
| **events** | Milestone, completed work, shipped artifact | "v0.3.2 was released to PyPI" |
| **emotional** | User-felt frustration/relief/excitement/pride — **high salience required** | "the backend bug you struggled with for 3 days was solved → win moment" |

**Emotional hall critical rule:** Throwaway signals like generic
"thanks", "great", "cool" do not warrant a drawer. Only write one when
the session contains an explicitly marked intense moment. If the session
does not contain this, **DO NOT WRITE** an emotional drawer. If salience
is empty, the hall is empty too.

## WING / ROOM / ENTITY RULES

### Wing (canonicalize it)

Read the `project:` field from the refined session's frontmatter. That
will be the Wing. But:

- Normalize TR diacritics: `Satın Alma` and `Satin-Alma` are the same wing
- Case-insensitive match against existing: `mnemos` and `Mnemos` → `Mnemos`
- Spaces become hyphens
- Fallback: `General`

### Room (topic cluster within wing)

Place drawers belonging to the same topic under the same wing into the
same room. Reference the existing room names; if none, generate a
**short kebab-case** room name based on the session's main subject
(like `backend`, `frontend`, `deployment`, `auth`, `phase1-design`,
`session-log`).

- The session filename is `YYYY-MM-DD-<slug>` — extract the topic from the slug
- The session frontmatter `tags:` list can give a room hint, but `tags[0]`
  is NOT BLINDLY treated as the room (v0.3.2 hygiene rule)
- If the session is on a single subject, all drawers go into the same room
- If there are multiple distinct subjects, split into 2-3 rooms (rarely)

### Entity (person vs project)

- **Person:** human name (Mehmet, Ayşe, Tugra) — proper noun, name
- **Project:** product/project/module name (Mnemos, ProcureTrack, RFQ-Hazirlama)
- **NOT a tag:** `session-log`, `phase1`, `tdd`, `atomic-rebuild` are
  tags, they DO NOT GO into entities (v0.3.2 A6 hygiene)
- **Case-preserve:** preserve the original spelling (`ProcureTrack`, `mnemos`),
  but do case-insensitive match when deduplicating
- 2-6 entities per drawer; more is noise

## CHUNKING — SPLITTING INPUT INTO DRAWERS

The chunking strategy depends on the type determined in INPUT FORMAT DETECTION.

### Type A — Refined session chunking

Refined sessions are structured (Özet / Alınan Kararlar / Yapılanlar
/ Sonraki / Sorunlar). Each section produces a DIFFERENT number of drawers:

| Session section | Drawer production |
|---|---|
| **Özet** | NOT a drawer on its own — no hall can be assigned, assumed to be merged into the events section |
| **Alınan Kararlar** | Each decision is a separate `decisions` drawer (1 per item, but if several related items are a single decision, merge them) |
| **Yapılanlar** | Important milestones become `events` drawers (commit+summary, shipped feature, etc.) |
| **Sonraki Adımlar** | DO NOT WRITE a drawer — transient TODO, does not belong in the palace |
| **Sorunlar** | Each resolved problem is a `problems` drawer (if both root cause + fix are present) |
| **Preference hints** (in the body, "bundan sonra X" / "my rule is") | `preferences` drawer |
| **Emotional moments** (strong expression) | `emotional` drawer — ONLY at high salience |

**Target drawer count:** 3-8 drawers per average refined session
(~30-50 lines). Fewer is under-extraction, more is noise.

### Type B — Curated topic note chunking

Topic notes are organized as H1 + multiple H2s. Each `## H2` subsection
is a drawer candidate.

| Structure | Drawer production |
|---|---|
| **H1 title + intro prose** | NOT a drawer (general context, no hall can be assigned) |
| **Each H2 subsection** | 1 drawer based on hall inference (decisions / problems / events / preferences / emotional) |
| **Single sentence or shorter than 10 words under an H2** | SKIP — insufficient signal |
| **H3 sub-headings** | NOT their own drawer — merged into the body of the parent H2 drawer |

**Target drawer count:** 3-7 drawers per average topic note (~5-10 H2
subsections). Generic "Notlar" / "TODO"-style H2s are skipped.

### Type C — Memory file chunking

**One drawer per file** — already atomized, no splitting.

| Field | Drawer field |
|---|---|
| Frontmatter `name` | H1 title |
| Frontmatter `description` | First sentence of the prose (if needed) |
| Body (entire prose) | Drawer body — **Why** / **How to apply** blocks are preserved |
| Frontmatter `type` | Hall mapping (user/feedback→preferences, project/reference→events) |

Leave the **Why:** / **How to apply:** lines in the body as-is (the
memory system's own structure, valuable signal).

### Type D — MEMORY.md index

Don't write any drawer, just a SKIP line (INPUT FORMAT DETECTION §D).

## IMPORTANCE SCORE

`importance` field is between 0.0 and 1.0:

- 0.9-1.0: architectural decision, project pivot, major milestone
- 0.6-0.8: normal technical decision, completed feature, important bug fix
- 0.3-0.5: minor decision, small task, routine
- 0.0-0.2: rarely — only for low-salience emotional drawers

Default: 0.5. Bump up anything especially emphasized in the session.

## FILENAME COLLISION

If the same `<YYYY-MM-DD>-<slug>.md` already exists:
- `<YYYY-MM-DD>-<slug>-2.md`, `-3.md` (refine skill pattern)

If 2+ drawers from the same session go to the same hall, try to keep
the slugs different (slug from the first topic; the second is a
different topic → different slug already).

## SKIP CRITERIA

If the refined session has not already been skipped (refine-transcripts
SKIPs already filtered it out), most sessions yield at least 1-2
drawers. But still:

- If the session body is **only Sonraki Adımlar** (TODO list, no decisions) → SKIP
- If the session is shorter than 5 lines + contains no decision/problem/event → SKIP
- If no entity can be extracted and it's a generic "did X" sentence → SKIP

Skip format (single line):
```
SKIP <session-basename> — <10-word reason>
```

## PROCESSING FLOW (for each input file)

1. Read the `.md` file
2. **Format detect:** identify Type A/B/C/D using INPUT FORMAT DETECTION rules
   - Type D (MEMORY.md) → SKIP immediately, write `SKIP ... — index file` to the ledger
3. Collect metadata from frontmatter + path:
   - Type A: `project` → Wing, `date`, `tags`
   - Type B: `project` or `tags[0]` or filename → Wing; `date` (mtime if missing); filename → room
   - Type C: Claude Code project folder name in the path → Wing; filename stem → room; `type` → hall
4. Canonicalize Wing (use the existing palace hint)
5. Split the body in a type-appropriate way:
   - Type A: Özet / Kararlar / Yapılanlar / Sonraki / Sorunlar sections
   - Type B: H2 subsections
   - Type C: single drawer (no splitting)
6. For each drawer:
   - Determine the hall (Type A section-based, Type B content inference, Type C frontmatter `type`)
   - Determine the room (use the existing palace hint)
   - Extract entities
   - Score importance
   - Smart H1 title + prose body
   - Generate the filename slug
   - Write to `<palace-root>/wings/<Wing>/<room>/<hall>/<filename>.md`
7. Final summary: `<input-basename>: N drawers (decisions:X events:Y problems:Z preferences:W emotional:V)`

## QUALITY CHECK (for each drawer)

Check before Write:
- [ ] Is the frontmatter valid YAML?
- [ ] Has the Wing been canonicalized? (consistent with the existing palace)
- [ ] Is the hall one of the 5 values?
- [ ] Are the entities not tags (not session-log, phase1, etc.)?
- [ ] Does the H1 title describe the drawer content on its own?
- [ ] Is the source line type-appropriate? (Type A/B: `[[basename]]` wikilink; Type C: plain `memory/<filename>`)
- [ ] Is the prose between 30 and 200 words? (too short = worthless; too long = noise)
- [ ] Has any code block / terminal output / tool result LEAKED IN? (everything must be removed)

If you get stuck on an item → fix the drawer.

## LANGUAGE

The drawer is in whichever language is dominant in the session. Technical
terms (API, commit, SDK, framework names, file paths) remain in their
original English form.

## OUT OF SCOPE

- **Collecting code blocks:** DO NOT PUT any code block in the drawer.
  Only refer to it like "X was changed in this file".
- **Terminal output:** Never.
- **Long quotes:** Don't quote more than 1-2 sentences from the session.
- **Meta-commentary:** Don't write subjective commentary like "this
  decision will matter later". Just report what happened.

---

**Ready. Provide the refined session path(s) you want to process + the palace root.**
