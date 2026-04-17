"""CLI entrypoint for the detached background auto-refine worker."""
from __future__ import annotations

import argparse
from pathlib import Path

from mnemos.auto_refine import run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="mnemos auto-refine background worker")
    parser.add_argument("--vault", required=True)
    parser.add_argument("--projects-dir", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--reminder-active", required=True, choices=["0", "1"])
    parser.add_argument("--triggering-session-id", default="")
    parser.add_argument("--picked", nargs="*", default=[])
    args = parser.parse_args(argv)

    run(
        vault=Path(args.vault),
        projects_dir=Path(args.projects_dir),
        ledger_path=Path(args.ledger),
        picked=[Path(p) for p in args.picked],
        reminder_active=args.reminder_active == "1",
        started_at=args.started_at,
        triggering_session_id=args.triggering_session_id,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
