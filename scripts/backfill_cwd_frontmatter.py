"""Backfill cwd: field into existing Sessions/.md frontmatter.

One-off migration: for each refine-ledger OK row, read the JSONL's first
cwd field and write it to the corresponding Sessions/.md YAML frontmatter.
Idempotent — re-running does nothing if cwd already present.

Usage:
  python scripts/backfill_cwd_frontmatter.py --vault <path> --apply
  python scripts/backfill_cwd_frontmatter.py --vault <path> --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


DEFAULT_LEDGER = Path.home() / ".claude/skills/mnemos-refine-transcripts/state/processed.tsv"


@dataclass
class LedgerRow:
    jsonl: str
    session_md: str  # filename only, Sessions/-relative


@dataclass
class BackfillReport:
    updated: int = 0
    skipped_already_present: int = 0
    jsonl_missing: int = 0
    session_md_missing: int = 0
    no_cwd_in_jsonl: int = 0
    errors: int = 0
    total: int = 0


def extract_cwd_from_jsonl(path: Path) -> Optional[str]:
    """Return the first `cwd` field value from a JSONL file, or None."""
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                cwd = msg.get("cwd") if isinstance(msg, dict) else None
                if isinstance(cwd, str) and cwd.strip():
                    return cwd
    except OSError:
        return None
    return None


def parse_ledger(ledger: Path) -> List[LedgerRow]:
    """Return OK rows from refine ledger TSV."""
    rows: List[LedgerRow] = []
    if not ledger.exists():
        return rows
    with ledger.open("r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            parts = raw.rstrip("\n").split("\t")
            if len(parts) < 4:
                continue
            _ts, status, jsonl, session_md = parts[0], parts[1], parts[2], parts[3]
            if status != "OK":
                continue
            if not session_md or session_md == "none":
                continue
            rows.append(LedgerRow(jsonl=jsonl, session_md=session_md))
    return rows


def upsert_cwd_frontmatter(md_path: Path, cwd: str) -> bool:
    """Add cwd: field to YAML frontmatter if missing. Return True if file changed."""
    if not md_path.exists():
        return False
    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError:
        return False

    # Match YAML frontmatter block at file start
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    if not m:
        return False

    front = m.group(1)
    # Already has cwd?
    if re.search(r"^cwd:\s", front, re.MULTILINE):
        return False

    # Insert cwd: after project: line (preferred) or at end of frontmatter
    new_line = f"cwd: {cwd}"
    project_match = re.search(r"^(project:\s.*)$", front, re.MULTILINE)
    if project_match:
        new_front = front.replace(
            project_match.group(1),
            project_match.group(1) + "\n" + new_line,
            1,
        )
    else:
        new_front = front.rstrip() + "\n" + new_line

    new_text = text.replace(m.group(0), f"---\n{new_front}\n---\n", 1)
    md_path.write_text(new_text, encoding="utf-8")
    return True


def run_backfill(
    vault: Path,
    ledger: Path,
    apply: bool,
    report_fn=None,
) -> BackfillReport:
    """Process ledger, update matching Sessions/.md files. Return report."""
    rows = parse_ledger(ledger)
    report = BackfillReport(total=len(rows))
    sessions_dir = vault / "Sessions"

    for row in rows:
        md = sessions_dir / row.session_md
        if not md.exists():
            report.session_md_missing += 1
            continue
        cwd = extract_cwd_from_jsonl(Path(row.jsonl))
        if cwd is None:
            jsonl_p = Path(row.jsonl)
            if not jsonl_p.exists():
                report.jsonl_missing += 1
            else:
                report.no_cwd_in_jsonl += 1
            continue

        # Check: already has cwd? (for dry-run accurate counts)
        try:
            existing = md.read_text(encoding="utf-8")
            if re.search(r"^cwd:\s", existing, re.MULTILINE):
                report.skipped_already_present += 1
                continue
        except OSError:
            report.errors += 1
            continue

        if apply:
            try:
                if upsert_cwd_frontmatter(md, cwd):
                    report.updated += 1
                else:
                    report.errors += 1
            except OSError:
                report.errors += 1
        else:
            # dry-run: count what would happen
            report.updated += 1

        if report_fn:
            report_fn(md, cwd)

    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill cwd: field into Sessions/.md")
    parser.add_argument("--vault", required=True, help="Vault path (parent of Sessions/)")
    parser.add_argument(
        "--ledger",
        default=str(DEFAULT_LEDGER),
        help=f"Refine ledger path (default: {DEFAULT_LEDGER})",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--apply", action="store_true", help="Write changes")
    group.add_argument("--dry-run", action="store_true", help="Show what would change")
    args = parser.parse_args(argv)

    vault = Path(args.vault)
    ledger = Path(args.ledger)

    if not vault.exists():
        print(f"error: vault not found: {vault}", file=sys.stderr)
        return 2

    report = run_backfill(vault=vault, ledger=ledger, apply=args.apply)

    print()
    print("Backfill complete" + (" (dry-run — no changes written)" if args.dry_run else "") + ":")
    print(f"  Updated:       {report.updated} sessions (cwd added)")
    print(f"  Skipped:       {report.skipped_already_present} sessions (cwd already present)")
    print(f"  JSONL missing: {report.jsonl_missing} sessions (cannot derive cwd; briefing will ignore)")
    print(f"  No cwd in JSONL:{report.no_cwd_in_jsonl} sessions")
    print(f"  Session MD missing: {report.session_md_missing} ledger rows")
    print(f"  Errors:        {report.errors} sessions")
    print(f"  Total ledger OK rows: {report.total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
