---
name: mnemos-briefing
description: Build per-cwd project memory briefing by reading refined
  Sessions/.md files with matching cwd frontmatter + associated Mnemos
  drawers, then synthesizing an evolution-aware narrative (200-400 words).
  Invoked by SessionStart hook (non-interactive via claude --print) with
  the current cwd as argument. Output goes to stdout; wrapper writes it
  to <vault>/.mnemos-briefings/<cwd-slug>.md.
---

# Mnemos briefing skill

You will be given a single argument: an absolute cwd path. Your job is to
read the canonical prompt at `prompt.md` (sibling file in this skill
folder) and execute it exactly.

**Process:**
1. Read `<skill-folder>/prompt.md` for the full synthesis prompt.
2. Follow its CWD FILTER → CHRONOLOGY → TOKEN BUDGET → SYNTHESIS steps.
3. Write briefing markdown body to stdout. No frontmatter.

**Invocation examples** (for reference; the hook calls you non-interactively):
```
/mnemos-briefing "C:\Users\tugrademirors\OneDrive\Masaüstü\farcry"
/mnemos-briefing "C:\Projeler\mnemos"
```

**If the cwd has no matching Sessions/.md files:** emit exactly this
placeholder and exit:

```
No prior sessions recorded for this cwd yet. Mnemos will brief from the
next session onwards.
```

**Cost:** this skill uses Claude Code subscription quota (claude --print),
not ANTHROPIC_API_KEY. Typical cost: 1 LLM call per session-start,
20-40K input tokens (session summaries + drawer metadata), 500-1000 output.
