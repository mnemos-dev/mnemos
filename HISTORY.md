# Mnemos — Project History

The honest version of how Mnemos got here. Less a release log, more a record
of which bets paid off, which broke under measurement, and what we kept.

For the engineering-grade release-by-release diff see
[`CHANGELOG.md`](CHANGELOG.md).

---

## April 12, 2026 — The bet

Mnemos started with a hypothesis copied from the prevailing wisdom of
2025-era AI memory tools. **MemPalace** (42K stars), **mem0**, most LangChain
memory backends — all shared the same shape:

> Take long conversations. Slice them into small "atoms." Embed each atom.
> Search top-K. Synthesis happens later.

The belief was that small chunks would produce sharper embeddings, that
fragmentation was the path to recall, that a graph of atoms across sessions
would let an AI traverse a "memory palace" the way a human walks a room.

The first commit on April 12 was a small CLI and an MCP server with four
tools (`search`, `add`, `mine`, `status`), regex-only mining (no LLM
required), ChromaDB on disk, and a file watcher syncing markdown notes.
**v0.1.0 — First Breath** — published to PyPI as `mnemos-dev` the same day.

---

## April 13–14, 2026 — Phase 0, the foundation

Two days of work produced what looked like a real system. The L0–L3 memory
stack landed: a knowledge graph with temporal triples in SQLite, a dual
ChromaDB collection (raw conversation chunks + mined fragment "drawers")
merged with Reciprocal Rank Fusion, room detection across 72 folder/keyword
patterns, 172 markers (87 EN + 85 TR) across four halls (decisions,
preferences, problems, events). Sessions chunked as exchange pairs so a
question and its answer travelled together.

The first benchmark run on the LongMemEval harness scored **70% Recall@5**.
Same-day tuning — chunk size 3000 → 800, RRF fetch ×3, source-path metadata —
pushed it to **90%**. Phase 1 target was 95%, and the numbers said we were
close.

**v0.2.0 — Full Memory** shipped to PyPI April 14.

---

## April 15–19, 2026 — The first reality: this is for strangers

Phase 0 worked for us. It did not work for someone who'd never seen the
project before. There was no path from `pip install mnemos-dev` to "your
past sessions are now searchable."

**v0.3 series** — five sub-releases over five days — built the entire
first-run experience: the `mnemos init` wizard with discovery + a 3-way
[A]ll/[S]elective/[L]ater decision, the `.mnemos-pending.json` resumable
schema, the `mnemos import` family for ChatGPT/Slack/Claude.ai/markdown,
and the `mnemos-refine-transcripts` skill — a Claude Code skill that lives
inside the user's session and refines noisy JSONL transcripts into rich
markdown notes.

The skill carried a hard architectural line we drew here and kept forever
after:

> **Mnemos itself never calls an LLM API.** Refinement runs *inside the
> user's Claude Code session*, on their existing subscription quota.
> Mnemos costs the user nothing beyond what they already pay.

Then the SessionStart auto-refine hook (task 3.7) — a hook that fires every
time you open a Claude Code session, picks the last 3 unprocessed JSONLs,
and refines them in a detached background worker. The pilot exposed a chain
of six bugs that taught the project everything it needed to know about
Windows hook reliability: cmd.exe quote stripping, backslash-escape
mangling, `ANTHROPIC_API_KEY` env leaks (the one that secretly burned
billable API credits while we thought subscription auth was working), and
the `# mnemos-auto-refine` comment marker that died on cmd.exe and had to
be reborn as a `_managed_by` JSON field.

A week of plumbing. Worth every hour.

**v0.3.0 → v0.3.3** shipped to PyPI between April 15 and 19. Backend
parity test on April 17 ran ChromaDB and sqlite-vec separately on the same
benchmark and produced identical numbers to four decimal places — the
backend choice was reliability/environment fit, not recall quality.

---

## April 22–25, 2026 — The cracks

We started **v0.4 AI Boost (Phase 1)** — the plan was to use Anthropic API
calls to enrich the mining pipeline, score harder, classify drawers more
precisely, push Recall@5 above 95%.

Then we measured what we already had and the bet broke:

1. **The RRF score band collapsed.** With k=60, scores stayed pinned in the
   0.014–0.017 range. The "small chunks → sharp embeddings" hypothesis did
   not hold on conversational data. Every drawer looked equally relevant
   to every query, which is the same as no signal.

2. **LLM synthesis fed better from whole sessions than from atoms.** When
   a briefing prompt was given full Session notes, the output was crisp.
   When given fragment drawers, the output was hazy. The atomization
   pipeline was actively hurting downstream quality.

3. **The graph nobody walked.** 600 nodes, beautiful in `mnemos_graph`
   output. Humans never browsed it; AI never traversed it on its own.
   The palace had become a poster — pretty wallpaper, not a tool.

4. **The drawers were redundant.** 663 drawers carrying ~860 entity
   instances. About **half** were just wing names like `Mnemos`,
   `ProcureTrack`, `GYP`. The "unique entities" we thought we were
   indexing came out to roughly 40–60 across the whole vault.

The Phase 1 plan was already in flight. We cancelled it.

---

## April 25, 2026 — The pivot

Atomic-fragmentation paradigm, declared dead. **Narrative-first** in.

The reframe was small to write, large to live:

> Conversational memory is not about chunking. It is about **whole
> Sessions** as memory units, **sparse but meaningful links** between them
> (entity wikilinks + tags), and an **Identity Layer** — a persistent user
> profile distilled from all sessions, updated incrementally, that the AI
> reads as a base layer before any cwd-specific context.
>
> The AI you build memory for shouldn't "remember the conversations." It
> should **know the user**. That is what separates Mnemos from MemPalace
> and mem0.

The pivot was a **clean break**, not a soft deprecation. The mining
pipeline (~3,000 lines of code, ~200 tests) was deleted from the codebase.
The `legacy/atomic-paradigm` branch and the `v0.4.0-archived` tag were
preserved as fossils for anyone who wanted to study the failed bet.

---

## April 26, 2026 — v1.0.0a1 ships

The narrative-first alpha. Sessions/.md as the canonical unit, Identity
Layer scaffold, three-layer briefing skill (Identity 3K + cwd Sessions 8K
+ 1-hop wikilink cross-context 4K, hard cap 15K), recall pared down to
plain Sessions search + grep rescue.

Same day, a hotfix. The `recall_briefing.py` re-entry guard had been
placed *before* `--catchup` arg parsing, so the background subprocess
inherited `HOOK_ACTIVE_ENV=1` from its parent and hit the guard before it
could write a briefing cache. Result: **no cache had been written for any
cwd since v1.0 went live.** Two regression tests now stand watch over
that line.

Tag `v1.0.0a1` pushed; PyPI publish deferred.

---

## April 26–27, 2026 — The second reality, and v1.1.0

The v1.0 model triggered all its work at SessionStart — open a new Claude
Code session, refine any orphaned JSONLs, then brief. It worked on paper.
In practice the trigger was wrong:

- **X-close while idle** worked.
- **X-close mid-stream** caused SessionStart to face an in-progress JSONL
  it had to refine *synchronously* before it could brief, blocking the
  user's first prompt.
- **kill -9** orphaned the JSONL entirely until the next session in the
  same cwd, which might be hours or days away.
- **SessionStart re-entry from background subprocesses** kept tripping
  guards and required the regression coverage above.

The architectural answer was to invert the trigger: **refine when the
session ends, not when the next one starts.** A SessionEnd hook returns
in under 100 ms (Claude Code's X-close grace window is 5 s) and spawns a
detached worker that survives Claude Code's own termination. On Windows
that means `CREATE_BREAKAWAY_FROM_JOB` so the OS doesn't take the worker
down with the parent's job object; on POSIX, `start_new_session=True`.

The detached worker runs three stages sequentially: refine *this*
transcript, regenerate the cwd briefing, check whether the Identity Layer
is due for a delta refresh. SessionStart still has a sync fallback for
the cases SessionEnd missed (mid-stream X-close, kill -9, or hardware
failure). And a readiness gate now keeps SessionStart silent when too
little of the cwd's history has been refined yet — better no briefing
than a misleading one.

The v1.1 design spec was written April 26 (818 lines). The 55-task TDD
plan was written the same day (4,748 lines, 13 task groups). Implementation
ran the next day, parallel agents on independent groups where possible.

**Empirical validation on April 27** — three smoke tests on the author's
real `kasamd` vault: graceful `/exit`, briefing inject on a fresh cwd,
mid-stream X-close. All three green. The blank terminal window the user
saw briefly during `/exit` was the detached worker doing its three stages
and exiting cleanly — by design, not by accident.

**v1.1.0** shipped to GitHub April 27, 2026. 527 tests pass / 2 skip /
3 deselect. Zero Anthropic API calls anywhere in `mnemos/` or `skills/`
(CI grep enforces it on every push). PyPI upload deferred a day for a
final observation window.

---

## What stayed true

Across two paradigms, four major releases, and one full pivot, a small
set of commitments never moved:

- **Obsidian is the source of truth.** Every memory is a plain `.md` file
  the user can read, edit, or delete by hand. ChromaDB and sqlite-vec are
  rebuildable indexes, not storage.
- **Mnemos never calls an LLM API.** All LLM operations route through
  `claude --print` against the user's existing Claude Code subscription.
  CI grep blocks accidental imports; `_child_env()` strips
  `ANTHROPIC_API_KEY` from every spawned subprocess.
- **TDD on every feature.** The 527-test suite grew test-first; no
  feature lands without a failing test, then a minimal pass, then green.
- **Idempotent + atomic.** Hook installs are idempotent and reversible.
  Every settings.json write goes through tmp + `os.replace` with a
  timestamped backup. Re-running anything is safe.
- **The user owns their data.** No telemetry, no cloud component, no
  account. Delete the vault folder and you delete every memory.

---

## Lessons we paid for

The cheap version of these lessons is on the next person's plate.
The expensive version was on ours:

- **Small chunks don't beat narrative for conversational memory.** The
  RRF score band tells you when your fragmentation has run out of signal.
- **A graph nobody walks is a poster.** Build the traversal — by humans
  or by the AI — before you build the graph.
- **Hook reliability is harder than function correctness.** Six pilot
  bugs in v0.3.7 (cmd.exe quoting, env leaks, backslash escaping) were
  worth more than any benchmark.
- **Trigger on the close, not on the open.** SessionEnd has a known
  end-of-input. SessionStart has unknown-orphan-handling, which is
  always more work.
- **Subscription quota is a hard line.** The moment you start spending
  the user's API budget, every architecture decision warps. Refuse the
  shortcut; route through `claude --print`.

---

## What's next

- **v1.2.0** — Polish + LongMemEval benchmark on the v1.0 narrative
  paradigm (target Recall@5 ≥ 93%; the v0.x baseline of 90% was the
  pre-pivot signal that fragment-RRF had topped out).
- **v0.6.0** — Obsidian plugin (browse the memory palace inside
  Obsidian itself), multi-language markers (DE/ES/FR), demo video.
- **Identity Layer maturity** — bootstrap automation, refresh quality,
  the long-running question of how a "user identity" should evolve over
  a year of sessions rather than over a week.

If you've read this far: thank you. Mnemos is small, the codebase fits
in your head, and the bets we got wrong are documented on purpose. Bring
your own.

---

*Maintained at: <https://github.com/mnemos-dev/mnemos>*
*Latest release: <https://github.com/mnemos-dev/mnemos/releases/tag/v1.1.0>*
