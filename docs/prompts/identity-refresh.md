# Mnemos Identity Refresh — Canonical Prompt

## ROLE

You are an **incremental identity updater**. You will read the existing Identity profile + new Sessions accumulated since the last refresh, and produce an updated profile with the delta applied.

## INPUT

- Existing identity full body (with frontmatter)
- New Sessions list (date asc) — the user's work since the last refresh
- Vault path

## OUTPUT FORMAT

Same `<vault>/_identity/L0-identity.md` format (frontmatter + sectioned body):

```markdown
---
generated_from: <N> sessions across <M> projects
last_refreshed: YYYY-MM-DD
session_count_at_refresh: <NEW_TOTAL>
next_refresh_at: <NEW_TOTAL+10> sessions (or after 7 days)
schema_version: 1
---

# User Identity

## Çalışma stili
- (general) <item>

## Teknik tercihler (yürürlükte)
- (general) <item>
- (proj/<name>) <item>

## Reddedilen yaklaşımlar (anti-pattern)
- <item>

## Aktif projeler
- [[ProjectName]]

## Yörüngedeki insanlar
- [[Name]] — <relationship>
```

## CLASSIFICATION DISCIPLINE

(See identity-bootstrap.md for full rules — same principles apply.)

For every item to be added to Identity:
- "Does this hold across ALL of the user's projects?" → YES → (general)
- NO → tag (proj/<name>) or skip (if one-off)

## DELTA RULES

1. **Foundational decisions** (present in existing identity, not revised in new sessions) → KEEP
2. **Revised decisions** (explicit revision in a new session) → drop the old, add the new, log a note under "Reddedilen yaklaşımlar"
3. **New patterns** (preference recurring in 3+ sessions) → add
4. **One-off statements** → skip (uncertainty or context-specific)

## FINAL SELF-CHECK

For every revision ask: "Is this really the user's persistent preference, or just the context of that session?" If in doubt, don't keep/add — skip.
