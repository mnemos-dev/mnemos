---
name: mnemos-identity-refresh
description: Update <vault>/_identity/L0-identity.md by reading existing identity + new Sessions since last refresh. Synthesizes delta into updated profile, marks revised preferences explicitly, preserves identity-relevant decisions. Invoked from SessionEnd worker subprocess (non-interactive via claude --print) — no arguments needed beyond vault discovery.
---

# Mnemos identity-refresh skill

You will be invoked from a SessionEnd worker subprocess to update the user's
Identity Layer when trigger conditions met (configurable session delta + min days).

**Process:**
1. Read `<skill-folder>/prompt.md` for the canonical refresh prompt.
2. Locate vault root (env MNEMOS_VAULT or upward walk for mnemos.yaml).
3. Read existing `<vault>/_identity/L0-identity.md` (frontmatter session_count_at_refresh tells delta start).
4. Read NEW Sessions since last refresh (`<vault>/Sessions/*.md` sorted, slice from last_count).
5. Synthesize delta into updated identity (preserve foundational, mark revisions, classify general vs proj-specific).
6. Write updated body to stdout. Wrapper writes atomically + history snapshot.

**Token budget:** 150K hard cap (existing Sessions + new sessions + existing identity).

**Cost:** Subscription quota via claude --print. ~30s per fire.
