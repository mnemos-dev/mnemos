---
name: mnemos-briefing
description: Build per-cwd project memory briefing by combining 3 layers (Identity + cwd Sessions + 1-hop wikilink expansion), then synthesizing an evolution-aware narrative (400-600 words). Invoked by SessionStart hook (non-interactive via claude --print) with the current cwd as argument. Output goes to stdout; wrapper writes it to <vault>/.mnemos-briefings/<cwd-slug>.md.
---

# Mnemos briefing skill v2 (3-layer)

You will be given a single argument: an absolute cwd path. Your job is to
read the canonical prompt at `prompt.md` (sibling file in this skill folder)
and execute it exactly.

**Process:**
1. Read `<skill-folder>/prompt.md` for the full 3-layer synthesis prompt.
2. Execute Step 1 (Identity) → Step 2 (Cwd) → Step 3 (Cross-context) → Step 4 (Budget) → Step 5 (Synthesize).
3. Write briefing markdown body to stdout. No frontmatter.

**Token budget:** Hard cap 15K input. Output 400-600 words (~1K tokens).

**Cost:** This skill uses Claude Code subscription quota (claude --print), not ANTHROPIC_API_KEY. Typical cost: 1 LLM call per session-start.
