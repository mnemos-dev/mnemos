"""One-shot vault rebuild: clear mined drawers + sqlite-vec index, then re-mine.

Used to recover from the wing-case-split bug where frontmatter `project:` fields
with inconsistent casing produced duplicate wings in the index. Running under
the new Palace.canonical_wing pathway consolidates everything to a single
canonical casing.

Usage:
    python scripts/rebuild_vault_index.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

VAULT = Path(r"C:\Users\tugrademirors\OneDrive\Masaüstü\kasamd")

# Ensure we import the fixed mnemos package from the working copy, not any
# globally installed older version.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mnemos.config import load_config  # noqa: E402
from mnemos.server import MnemosApp  # noqa: E402


def _truncate_search_tables(sqlite_path: Path) -> None:
    """Drop mined/raw rows + their vec shadows. Schema stays intact."""
    import sqlite3

    import sqlite_vec

    conn = sqlite3.connect(str(sqlite_path), timeout=30)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        with conn:
            for table in ("mined", "raw", "vec_mined", "vec_raw"):
                try:
                    conn.execute(f"DELETE FROM {table}")
                except sqlite3.OperationalError as exc:
                    print(f"  skip {table}: {exc}")
    finally:
        conn.close()


def _wipe_drawer_files(wings_dir: Path) -> int:
    """Remove drawer .md files under each wing, keep _wing.md / _room.md."""
    if not wings_dir.exists():
        return 0
    removed = 0
    for wing in wings_dir.iterdir():
        if not wing.is_dir():
            continue
        for path in wing.rglob("*.md"):
            if path.name in {"_wing.md", "_room.md"}:
                continue
            path.unlink()
            removed += 1
        # Remove now-empty hall/room dirs for cleanliness (best-effort; OneDrive
        # can briefly lock directories, and empty-dir cleanup is cosmetic).
        for sub in sorted(wing.rglob("*"), key=lambda p: -len(p.parts)):
            if sub.is_dir() and not any(sub.iterdir()):
                try:
                    sub.rmdir()
                except OSError:
                    pass
    return removed


def _remove_lowercase_duplicates(wings_dir: Path) -> None:
    """On case-sensitive filesystems the duplicate ``mnemos`` dir would sit
    beside ``Mnemos``. On Windows (case-insensitive) only one exists, so this
    is a no-op. Kept for parity on cross-platform reruns."""
    if not wings_dir.exists():
        return
    seen: dict[str, Path] = {}
    for p in wings_dir.iterdir():
        if not p.is_dir():
            continue
        key = p.name.lower()
        if key in seen:
            shutil.rmtree(p)
            print(f"  merged duplicate {p.name} -> {seen[key].name}")
        else:
            seen[key] = p


def main() -> None:
    cfg = load_config(str(VAULT))
    palace_dir = cfg.palace_dir
    wings_dir = cfg.wings_dir
    sqlite_path = palace_dir / "search.sqlite3"
    mine_log = cfg.mine_log_full_path

    print(f"Vault:       {VAULT}")
    print(f"Palace:      {palace_dir}")
    print(f"Wings:       {wings_dir}")
    print(f"Search idx:  {sqlite_path}")
    print(f"Mine log:    {mine_log}")
    print()

    print("[1/4] Truncating search tables...")
    if sqlite_path.exists():
        _truncate_search_tables(sqlite_path)
    else:
        print("  (no index file; will be created on first mine)")

    print("[2/4] Wiping drawer files under wings/...")
    removed = _wipe_drawer_files(wings_dir)
    print(f"  removed {removed} drawer file(s)")
    _remove_lowercase_duplicates(wings_dir)

    print("[3/4] Clearing mine.log...")
    if mine_log.exists():
        mine_log.unlink()
        print("  mine.log deleted")

    print("[4/4] Re-mining Sessions/ and Topics/ with fresh code...")
    with MnemosApp(cfg) as app:
        for sub in ("Sessions", "Topics"):
            target = VAULT / sub
            if not target.exists():
                print(f"  {sub}/: missing, skipping")
                continue
            result = app.handle_mine(path=str(target))
            print(f"  {sub}/: {result}")

        stats = app.handle_status()
    print()
    print("Final status:")
    print(stats)


if __name__ == "__main__":
    main()
