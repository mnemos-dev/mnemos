# Async SUB-B2 recall briefing — design spec

**Status:** approved, implementation pending
**Date:** 2026-04-24
**Owner:** recall_briefing hook

## Context

The v0.4 recall hook's SUB-B2 "blocking catch-up" path is synchronous:
on every session start where the current cwd has at least one unrefined
JSONL, the hook runs `refine → mine → brief` sequentially for up to
`SUB_B2_PENDING_CAP = 3` JSONLs before emitting `additionalContext`.
Each `claude --print` subprocess costs ~60-120s, so the user waits 2-5
minutes between typing their first prompt and seeing any response — the
smoke test on mnemos cwd measured 5 minutes flat.

The blocking design assumed "the user needs the most recent session
reflected in the briefing on the very next open". In practice, the
briefing's value is cumulative context, not a 90-second-fresh summary.
Missing the last session by one open is imperceptible; waiting 5
minutes every single session is a dealbreaker.

## Change

Replace blocking SUB-B2 with an async pipeline. `handle_session_start`
returns in <1s in every branch. Pending JSONLs are processed by a
detached background subprocess, which also regenerates the cache so
the *next* session opens with fresh content.

### New decision tree

Return-visit (CASE B):

| pending | cache | behavior | outcome |
|---|---|---|---|
| 0 | present | inject cache, bg regen (existing) | `fast_path_injected` |
| 0 | missing | bg brief spawn, no inject (existing) | `fast_path_no_cache` |
| 1+ | present | **inject cache, bg catchup spawn** | `fast_path_injected_with_catchup` |
| 1+ | missing | **bg catchup spawn, no inject** | `bg_catching_up` |

SUB-B2's `refine → mine → brief` chain now runs in the detached bg
subprocess instead of the hook process. The hook itself never blocks
on subprocess work.

### Removed: staleness threshold

The current `STALE_THRESHOLD = 3` (session-count diff triggering sync
regen) is deleted. Every bg spawn — fast-path with cache or catchup —
writes a fresh cache, so the threshold becomes redundant. One rule,
one behavior.

### New foreground function: `catchup_and_cache(cwd, vault)`

Extends `brief_and_cache` by prepending the refine+mine loop:

```
catchup_and_cache(cwd, vault):
    pending = find_unrefined_jsonls_for_cwd(cwd_slug, ...)
    pending = pending[-SUB_B2_PENDING_CAP:]  # last N most-recent
    for jsonl in pending:
        refine_result = run_refine_sync(jsonl)
        if refine_result.ok:
            session_md = _lookup_session_md_in_ledger(ledger, jsonl)
            if session_md:
                run_mine_sync(vault / "Sessions" / session_md)
    return brief_and_cache(cwd, vault)  # existing brief + cache write
```

### New subcommand: `--catchup`

`main()` accepts `--catchup --cwd X --vault Y` and dispatches to
`catchup_and_cache(X, Y)`. Single bg entry — `catchup_and_cache`
already short-circuits the refine+mine loop when pending is empty,
so the same subcommand serves both fast-path cache regen and real
catch-up work. Old `--brief-and-cache` + `_spawn_bg_brief` retained
as internal helpers (used by `catchup_and_cache`; no external
surface change).

### Implementation delta

- `recall_briefing.py`: remove `_run_sub_b2`. Delete `STALE_THRESHOLD`
  branch. `SUB_B2_PENDING_CAP` now applied inside `catchup_and_cache`.
- Add `catchup_and_cache(cwd, vault)` function (wraps existing
  `brief_and_cache` with a pending refine+mine prelude).
- Add `_spawn_bg_catchup(cwd, vault)` — Popen detached, invokes
  `python -m mnemos.recall_briefing --catchup ...`. Replaces
  `_spawn_bg_brief` at call sites.
- Modify `handle_session_start`: every pending-or-no-cache branch now
  calls `_spawn_bg_catchup`. Cache presence still decides inject vs
  silent. No sync subprocess calls in the hook path.
- `main()` adds `--catchup` dispatch (keeps `--brief-and-cache` for
  backward-compat / test import).

## Tests

1. Return-visit with pending + cache → outcome
   `fast_path_injected_with_catchup`, bg catchup spawn happened, cache
   body returned for inject.
2. Return-visit with pending + no cache → outcome `bg_catching_up`,
   bg catchup spawn, no inject.
3. Return-visit with no pending + cache → unchanged (`fast_path_injected`).
4. Return-visit with no pending + no cache → unchanged (`fast_path_no_cache`).
5. `catchup_and_cache` runs refine → mine → brief in order, writes
   cache, returns True on all-ok path.
6. `catchup_and_cache` with refine failure → skips mine for that JSONL,
   continues with remainder, still produces cache.
7. `--catchup` subcommand dispatches to `catchup_and_cache`, does not
   read stdin, does not touch hook state.
8. Existing 4 SUB-B2 sync tests: removed (behavior gone) or rewritten
   to exercise the new async path.

## Out of scope

- Tuning `SUB_B2_PENDING_CAP` — stays at 3, relevant only to the bg
  worker's loop bound.
- Staleness return behavior — one global rule: bg always regenerates.
- User-facing progress surface — hook-status.json continues to reflect
  whatever the bg subprocess writes; statusline snippet unchanged.

## Acceptance criteria

- Hook latency <1 second on every session start in every branch
  (measured via timing around `handle_session_start`).
- mnemos cwd (pending=1) smoke: 2nd session after ship opens with
  briefing injected (cache created by prior bg catchup).
- Test suite: 637 → 637 ± 2 (net test count stable after SUB-B2
  rewrites).

## Risks

- **Bg subprocess silent death:** already a known v0.4.1 polish item
  (P8 in STATUS). If `_spawn_bg_catchup` dies without writing cache,
  the next session opens silent again. Mitigation: same pattern as
  existing `_spawn_bg_brief` (already deployed for `fast_path_injected`
  regen); no new silent-death surface.
- **Cache staleness drift:** if user opens 10 sessions in an hour and
  the bg catchup can't keep up (each one is ~3 min on real vault), the
  briefing accumulates lag. Mitigation: cap=3 limits bg work per fire;
  empirical observation will show whether this is a real issue. Not
  addressed in this spec.
