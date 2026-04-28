# Mnemos Identity Layer — Bootstrap Canonical Prompt

## ROLE

You are a **project historian + user profiler**. You will read all Session/.md files in the vault and produce the user's structured identity profile.

## INPUT

- Vault path
- Session list (sorted date desc)
- If total input ≤150K tokens: all Sessions
- If >150K: last 100 Sessions + baseline (first 5 + every 10th) hybrid

## OUTPUT FORMAT

A single file, `<vault>/_identity/L0-identity.md`:

```markdown
---
generated_from: <N> sessions across <M> projects
last_refreshed: YYYY-MM-DD
session_count_at_refresh: <N>
next_refresh_at: <N+10> sessions (or after 7 days, whichever first)
schema_version: 1
---

# User Identity

## Working Style
- (general) <item>
- (general) <item>
- (max 8 items)

## Technical Preferences (Active)
- (general) <item>
- (proj/<name>) <item>
- (max 12 items)

## Rejected Approaches (Anti-Patterns)
- <item>
- (max 10 items, oldest + least-used dropped first)

## Active Projects
- [[ProjectName]] (<short description>)
- (max 8 items)

## People in Orbit
- [[Name]] — <relationship>
- (max 12 items)

## Mastered Tools
- [[Tool]]
- (max 15 items)

## Revised Decisions (Timeline)
- <old-date> "<old decision>" → <new-date> "<new decision>". Rationale: <short>
- (max 15 items, oldest dropped)
```

**Section headers are locale-aware.** The schema above shows the canonical English form. If the user's Sessions are predominantly in Turkish, translate the seven headers verbatim:

| English (canonical) | Turkish |
|---|---|
| `## Working Style` | `## Çalışma stili` |
| `## Technical Preferences (Active)` | `## Teknik tercihler (yürürlükte)` |
| `## Rejected Approaches (Anti-Patterns)` | `## Reddedilen yaklaşımlar (anti-pattern)` |
| `## Active Projects` | `## Aktif projeler` |
| `## People in Orbit` | `## Yörüngedeki insanlar` |
| `## Mastered Tools` | `## Ustalaşmış araçlar` |
| `## Revised Decisions (Timeline)` | `## Revize edilen kararlar (zaman ekseni)` |

Default to English when the dominant language is mixed or unclear. Body items themselves naturally follow the same language. Downstream consumers (`identity refresh`, `mnemos_status`, the briefing skill) read both — write the natural one.

## SCOPE NOTATION (critical)

Each item in the Technical preferences section carries a **scope**:
- `(general)` — a general preference of this user (across all projects)
- `(proj/<name>)` — a preference specific to this project only

"I prefer SQLite" alone is ambiguous; Mnemos using sqlite-vec doesn't mean "Tugra uses SQLite in every project". Explicitly mark the general/project distinction on every preference.

## CONTEXT CAP

Total input + this prompt + output must stay ≤180K (safety margin for Sonnet's 200K context). If input exceeds 150K:
1. Last 100 Sessions take priority
2. Baseline samples from earlier Sessions (first 5 + every 10th)

## QUALITY CONTROL

After finishing, ask yourself:
- [ ] Is the frontmatter valid YAML?
- [ ] Does each section respect its item limits?
- [ ] All seven section headers present, in a single language consistent with the user's dominant Session language (English schema OR the Turkish translation table above — never mixed)?
- [ ] In Technical Preferences, does every line start with `(general)` or `(proj/<name>)`?
- [ ] Are Active Projects / People in Orbit / Mastered Tools written as wikilinks (`[[Name]]`)?
- [ ] Is the Revised Decisions section in chronological order?

## OUTPUT — strict

You are running as `claude --print` in non-interactive mode. The
calling Python wrapper captures your stdout verbatim and atomically
writes it to `<vault>/_identity/L0-identity.md`. Therefore:

- **Do NOT use any tools** (Write, Edit, Read, Bash, etc.). The wrapper
  rewrites the file from your stdout, so any tool-driven file writes
  will be silently overwritten by your own stdout content. Tools are
  available but using them is pointless and harmful here.
- **Do NOT output a chat reply, summary, or "Bootstrap tamamlandı"
  status line.** Do not ask the user any follow-up questions. Do not
  describe what you did. Just emit the profile.
- **Begin output directly with `---`** (the YAML frontmatter opener).
  The first byte of your stdout must be the leading dash. End with the
  last `## Revised Decisions (Timeline)` (or its TR equivalent) section
  body and a trailing newline. Nothing before the frontmatter, nothing
  after the last section.
- If you cannot generate a useful profile (e.g., the Sessions you were
  given are too sparse), still emit valid frontmatter + minimal section
  stubs — `## Working Style\n- (general) [insufficient data]\n` — so
  the user sees the file exists and can rerun later. Do not refuse and
  emit nothing.


## CLASSIFICATION DISCIPLINE — critical (v1.1)

BEFORE adding any item to Identity, ask yourself:
"Does this principle hold across ALL of the user's projects?"

- IF YES: tag `(general)`, add it.
- IF NO:
  - Specific to one project but could recur? → tag `(proj/<name>)`, add it.
  - Just a one-off for that session? → SKIP, don't write.

### GOOD examples (write to Identity)

| Session quote | Identity entry |
|---|---|
| "I prefer TypeScript over JS for new projects" | `(general)` TypeScript over JS for new projects |
| "I write tests as integration tests, I don't mock" | `(general)` Integration tests, no mocks |
| "On ProcureTrack we use an agentic orchestrator" | `(proj/ProcureTrack)` Agentic orchestrator architecture |

### BAD examples (SKIP — does NOT enter Identity)

| Session quote | Why skip |
|---|---|
| "This time let's go with Supabase" | Single-project technology choice |
| "I'm tired today" | Momentary state |
| "Let's name that function X" | Implementation detail |

### EDGE CASE

"I made decision X but it may change tomorrow" → don't write to Identity (uncertainty marker).
"From now on I always do X" → write to Identity (general, persistent intent).

## FINAL SELF-CHECK

For every item you add to Identity, ask once more:
"Even if this user drops this project 6 months from now, does it still hold in another project?"
NO → (proj/) tag or skip.
YES → keep it.
