# Security policy

## Supported versions

Mnemos is pre-1.0. Security fixes land on the **latest minor release only**.
Upgrade to the newest `0.x.y` before reporting a vulnerability — if the
issue is already patched there, an upgrade is the fix.

| Version | Supported          |
|---------|--------------------|
| 0.3.x   | ✅ (latest minor)  |
| < 0.3   | ❌                 |

## Reporting a vulnerability

**Please do not open a public GitHub issue for security reports.**

Use GitHub's private vulnerability reporting instead:

- Go to <https://github.com/mnemos-dev/mnemos/security/advisories/new>
- Describe the issue, reproduction steps, and the impact you observed.
- Include the mnemos version and backend (chromadb / sqlite-vec).

You should get an acknowledgement within **7 days**. Fix-in-flight and
disclosure timing are negotiated in the advisory thread.

## What's in scope

Mnemos runs locally, reads your Obsidian vault and Claude Code JSONL
transcripts, and (optionally) calls the Claude API via `mnemos-dev[llm]`.
Security-relevant areas:

- **Path traversal / write-outside-vault** — mining or refine paths
  escaping the configured vault root.
- **Arbitrary command execution** — the auto-refine hook spawns
  `claude --print`. Injection into that command line.
- **Secret leakage** — API keys or tokens accidentally written to
  drawers, logs, or the `.mnemos-hook-status.json` file.
- **Denial-of-service** on the user's own machine — a crafted transcript
  or `mnemos.yaml` that hangs the miner or fills disk.

## What's out of scope

- Obsidian itself, ChromaDB, sqlite-vec, or Claude Code — report those
  upstream.
- Issues that require already-root/admin on the machine.
- Anything that depends on the user intentionally installing a hostile
  plugin or skill.
