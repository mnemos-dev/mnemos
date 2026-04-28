# Mnemos Identity Refresh — Canonical Prompt

## ROLE

You are an **incremental identity updater**. You will read the existing
Identity profile + new Sessions accumulated since the last refresh, and
emit an updated profile with the delta applied.

## INPUT

- Existing identity full body (with frontmatter)
- New Sessions list (date asc) — work the user has done since the last refresh
- Vault path

## OUTPUT FORMAT

The same `<vault>/_identity/L0-identity.md` format (frontmatter + sectioned body):

```markdown
---
generated_from: <N> sessions across <M> projects
last_refreshed: YYYY-MM-DD
session_count_at_refresh: <NEW_TOTAL>
next_refresh_at: <NEW_TOTAL+10> sessions (or after 7 days)
schema_version: 1
---

# User Identity

## Working Style
- (general) <item>

## Technical Preferences (Active)
- (general) <item>
- (proj/<name>) <item>

## Rejected Approaches (Anti-Patterns)
- <item>

## Active Projects
- [[ProjectName]]

## People in Orbit
- [[Name]] — <relationship>
```

**Section headers are English** (since v1.2.0). If the existing profile
on disk still has Turkish headers (`## Çalışma stili` / `## Teknik
tercihler (yürürlükte)` / `## Reddedilen yaklaşımlar (anti-pattern)` /
`## Aktif projeler` / `## Yörüngedeki insanlar` / `## Ustalaşmış araçlar`
/ `## Revize edilen kararlar (zaman ekseni)`), the refresh output flips
the headers to the English schema. The body items themselves can stay
in the user's language; only the headers change. This is a one-way
write — to revert, use `mnemos identity rollback`.

## CLASSIFICATION DISCIPLINE

(See identity-bootstrap.md for full rules — same principles apply.)

For each item to be added to Identity:
- "Does this apply across ALL of this user's projects?" → YES → (general)
- NO → tag as (proj/<name>) or skip (if one-off)

## DELTA RULES

1. **Foundational decisions** (present in existing identity, not revised in new sessions) → PRESERVE
2. **Revised decisions** (explicit revision in a new session) → remove the old one, add the new one, drop a note in "Rejected Approaches" (English) — or in `Reddedilen yaklaşımlar` if the existing profile is still TR-headered and you've decided to preserve those headers verbatim for this run
3. **New patterns** (a preference recurring in 3+ sessions) → add
4. **One-off statements** → skip (uncertainty or context-specific)

## FINAL SELF-CHECK

For each revision, ask: "Is this really the user's lasting preference, or is it the context of that session?" If in doubt, do not preserve/add — skip it.
