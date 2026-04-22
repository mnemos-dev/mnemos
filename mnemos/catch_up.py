"""Foreground bulk processor for backlog (Spec §6.3).

Shares helpers with the SessionStart auto-refine hook but runs in the user's
terminal with progress prints and optional parallelism. Invoked via
``mnemos catch-up`` subcommand.

Not to be confused with ``mnemos mine --pilot-llm`` — that command produces a
pilot palace under Mnemos-pilot/ for a batch compare + accept; catch-up writes
directly into the production palace under Mnemos/ (accept-bypass, hook-style).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

Runner = Callable[[list[str]], int]


@dataclass
class CatchUpResult:
    processed: int
    errors: int
    deferred: int


def _confirm(prompt: str) -> bool:
    try:
        return input(prompt).strip().lower() in {"y", "yes"}
    except EOFError:
        return False


def run_catch_up(
    *,
    vault: Path,
    projects_dir: Path,
    refine_ledger_path: Path,
    mine_ledger_path: Path,
    limit: int | None = None,
    parallel: int = 1,
    dry_run: bool = False,
    yes: bool = False,
    runner: Runner | None = None,
) -> CatchUpResult:
    """Run the skill-mine pipeline as a foreground batch.

    Enforces ``mine_mode: skill`` — raises ``CatchUpError`` otherwise so users
    don't accidentally mix regex and skill mining in one pass.
    """
    from mnemos.auto_refine import (
        _read_mine_mode,
        _pick_unmined_sessions,
        _pick_unprocessed_jsonls,
        _run_skill_pipeline,
        _default_runner,
    )

    if _read_mine_mode(vault) != "skill":
        raise CatchUpError(
            "mnemos catch-up requires mine_mode: skill in mnemos.yaml. "
            "Set it manually or run `mnemos mine --pilot-llm` + accept first."
        )

    palace_root = Path(vault) / "Mnemos"
    runner = runner or _default_runner

    # Compute plan
    cap = limit if (limit is not None and limit > 0) else 10_000_000
    unmined = _pick_unmined_sessions(
        vault=vault, mine_ledger_path=mine_ledger_path,
        palace_root=palace_root, limit=cap,
    )
    remaining_after_a = cap - len(unmined)
    unrefined = _pick_unprocessed_jsonls(
        projects_dir=projects_dir, ledger_path=refine_ledger_path,
        limit=max(0, remaining_after_a),
    )
    total = len(unmined) + len(unrefined)

    print("Plan:")
    print(f"  Phase A (unmined Sessions):      {len(unmined)}")
    print(f"  Phase B (unrefined JSONLs):      {len(unrefined)}")
    print(f"  Will process:                    {total}"
          + (f" (limit={limit})" if limit else ""))
    if parallel > 1:
        print(f"  Parallelism:                     {parallel} workers")
        print(f"  Warning: {parallel} concurrent claude subprocesses will hit your")
        print(f"  Claude Code subscription — ensure your plan allows it.")

    if dry_run or total == 0:
        return CatchUpResult(processed=0, errors=0, deferred=0)

    if not yes and not _confirm(f"Proceed? [y/N] "):
        print("Aborted.")
        return CatchUpResult(processed=0, errors=0, deferred=total)

    # If parallel == 1, one call to _run_skill_pipeline does everything.
    # If parallel > 1, shard the total work across N worker pipelines. Each
    # worker owns a slice of Phase A + Phase B independently. The skill-mine
    # ledger guarantees no two workers mine the same source twice (different
    # processes, but ledger is append-only file-locked by each claude
    # subprocess; duplicate claims simply resolve to ledger-skipped).
    if parallel <= 1:
        _run_skill_pipeline(
            vault=vault, projects_dir=projects_dir,
            refine_ledger_path=refine_ledger_path,
            mine_ledger_path=mine_ledger_path,
            runner=runner, cap=cap,
            on_phase=_print_phase,
        )
        return CatchUpResult(processed=total, errors=0, deferred=0)

    # Parallel: shard Phase A first (each worker grabs unmined_slice),
    # then shard Phase B (each worker grabs unrefined_slice).
    def worker_slice(items, worker_idx):
        return items[worker_idx::parallel]

    with ThreadPoolExecutor(max_workers=parallel) as ex:
        for worker_idx in range(parallel):
            a_slice = worker_slice(unmined, worker_idx)
            b_slice = worker_slice(unrefined, worker_idx)
            ex.submit(
                _run_skill_pipeline,
                vault=vault, projects_dir=projects_dir,
                refine_ledger_path=refine_ledger_path,
                mine_ledger_path=mine_ledger_path,
                runner=runner, cap=len(a_slice) + len(b_slice),
                on_phase=_print_phase,
            )
    return CatchUpResult(processed=total, errors=0, deferred=0)


def _print_phase(phase: str, i: int, total: int, source: Path) -> None:
    print(f"  [{phase} {i}/{total}] {source.name}")


class CatchUpError(Exception):
    """Raised when catch-up preconditions are not met (e.g. mine_mode: script)."""
