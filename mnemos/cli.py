"""Mnemos CLI — init, mine, search, status commands."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import yaml

from mnemos.config import load_config, HALLS_DEFAULT, WATCHER_IGNORE_DEFAULT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_vault(args_vault: Optional[str]) -> str:
    """Return vault path: CLI flag > env var > empty string."""
    if args_vault:
        return str(Path(args_vault).expanduser().resolve())
    import os
    return os.environ.get("MNEMOS_VAULT", "")


def _require_vault(vault_path: str, cmd: str) -> None:
    """Exit with a helpful message if vault_path is empty."""
    if not vault_path:
        sys.exit(
            f"[mnemos {cmd}] No vault path found.\n"
            "Pass --vault <path>, set MNEMOS_VAULT env var, "
            "or run `mnemos init` first."
        )


# ---------------------------------------------------------------------------
# cmd_init
# ---------------------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> None:
    """Interactive wizard: scaffold a Mnemos vault."""
    print("=== Mnemos Init Wizard ===\n")

    # --- Vault path ---
    if args.vault:
        vault_path = str(Path(args.vault).expanduser().resolve())
        print(f"Using vault path: {vault_path}")
    else:
        raw = input("Vault path (Obsidian vault root): ").strip()
        if not raw:
            sys.exit("Vault path cannot be empty.")
        vault_path = str(Path(raw).expanduser().resolve())

    vault_dir = Path(vault_path)
    if not vault_dir.exists():
        create = input(f"  Directory does not exist. Create it? [y/N] ").strip().lower()
        if create == "y":
            vault_dir.mkdir(parents=True, exist_ok=True)
            print(f"  Created: {vault_dir}")
        else:
            sys.exit("Aborted.")

    # --- Languages ---
    raw_langs = input("Languages (comma-separated, e.g. en,tr) [en]: ").strip()
    languages = [l.strip() for l in raw_langs.split(",") if l.strip()] if raw_langs else ["en"]

    # --- LLM ---
    use_llm_raw = input("Enable LLM-assisted mining? [y/N]: ").strip().lower()
    use_llm = use_llm_raw == "y"

    # --- Build config ---
    config_data: dict = {
        "vault_path": vault_path,
        "languages": languages,
        "use_llm": use_llm,
        "halls": list(HALLS_DEFAULT),
        "watcher_ignore": list(WATCHER_IGNORE_DEFAULT),
    }

    # --- Write mnemos.yaml ---
    yaml_path = vault_dir / "mnemos.yaml"
    if yaml_path.exists():
        overwrite = input(f"\n  mnemos.yaml already exists. Overwrite? [y/N]: ").strip().lower()
        if overwrite != "y":
            print("  Keeping existing mnemos.yaml.")
        else:
            yaml_path.write_text(yaml.dump(config_data, allow_unicode=True), encoding="utf-8")
            print(f"  Wrote: {yaml_path}")
    else:
        yaml_path.write_text(yaml.dump(config_data, allow_unicode=True), encoding="utf-8")
        print(f"\n  Wrote: {yaml_path}")

    # --- Create palace structure ---
    from mnemos.config import MnemosConfig
    from mnemos.palace import Palace

    cfg = MnemosConfig(
        vault_path=vault_path,
        languages=languages,
        use_llm=use_llm,
    )
    palace = Palace(cfg)
    palace.ensure_structure()
    print(f"  Created palace structure at: {cfg.palace_dir}")

    # --- Identity placeholder ---
    identity_file = cfg.identity_full_path / "L0-identity.md"
    if not identity_file.exists():
        identity_file.write_text(
            "---\ntype: identity\nlevel: L0\n---\n\n"
            "# Identity\n\n"
            "This is your Mnemos identity file. "
            "Describe yourself, your goals, and your preferences here.\n",
            encoding="utf-8",
        )
        print(f"  Created identity placeholder: {identity_file}")

    # --- Offer to mine existing files ---
    print()
    mine_now = input("Mine existing markdown files in the vault now? [y/N]: ").strip().lower()
    if mine_now == "y":
        print("  Mining vault (this may take a while)...")
        from mnemos.server import MnemosApp

        app = MnemosApp(cfg)
        result = app.handle_mine(path=vault_path, use_llm=use_llm)
        print(
            f"  Done — scanned: {result['files_scanned']}, "
            f"drawers: {result['drawers_created']}, "
            f"entities: {result['entities_found']}, "
            f"skipped: {result['skipped']}"
        )

    # --- MCP connection instructions ---
    print(
        "\n=== MCP Connection ===\n"
        "Add the following to your Claude Desktop / Cursor MCP config:\n\n"
        '  "mnemos": {\n'
        '    "command": "mnemos",\n'
        '    "args": ["serve"],\n'
        f'    "env": {{"MNEMOS_VAULT": "{vault_path}"}}\n'
        "  }\n\n"
        "Then restart your MCP client.\n"
        "\nSetup complete!"
    )


# ---------------------------------------------------------------------------
# cmd_mine
# ---------------------------------------------------------------------------


def cmd_mine(args: argparse.Namespace) -> None:
    """Mine a file or directory and print results as JSON."""
    vault_path = _resolve_vault(args.vault)
    _require_vault(vault_path, "mine")

    cfg = load_config(vault_path)

    from mnemos.server import MnemosApp

    app = MnemosApp(cfg)

    if args.rebuild:
        app._mine_log = {}
        app._save_mine_log()
        print("Rebuild: mine_log cleared, re-mining all sources...")

    result = app.handle_mine(
        path=args.path,
        use_llm=args.llm,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# cmd_search
# ---------------------------------------------------------------------------


def cmd_search(args: argparse.Namespace) -> None:
    """Search the memory palace and print formatted results."""
    vault_path = _resolve_vault(args.vault)
    _require_vault(vault_path, "search")

    cfg = load_config(vault_path)

    from mnemos.server import MnemosApp

    app = MnemosApp(cfg)
    results = app.handle_search(
        query=args.query,
        wing=args.wing,
        hall=args.hall,
        limit=args.limit,
    )

    if not results:
        print("No results found.")
        return

    for i, r in enumerate(results, 1):
        score = r.get("score", 0.0)
        wing = r.get("wing", "?")
        hall = r.get("hall", "?")
        text = r.get("text", "").strip()
        # Truncate long texts for readability
        preview = text[:200] + "..." if len(text) > 200 else text
        print(f"[{i}] score={score:.3f}  wing={wing}  hall={hall}")
        print(f"     {preview}")
        print()


# ---------------------------------------------------------------------------
# cmd_status
# ---------------------------------------------------------------------------


def cmd_status(args: argparse.Namespace) -> None:
    """Print memory palace status as JSON."""
    vault_path = _resolve_vault(args.vault)
    _require_vault(vault_path, "status")

    cfg = load_config(vault_path)

    from mnemos.server import MnemosApp

    app = MnemosApp(cfg)
    result = app.handle_status()
    print(json.dumps(result, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# main — argparse entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="mnemos",
        description="Mnemos — Obsidian-native AI memory palace",
    )
    parser.add_argument(
        "--vault",
        metavar="PATH",
        default=None,
        help="Path to the Obsidian vault root (overrides MNEMOS_VAULT env var)",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    subparsers.required = False

    # ------------------------------------------------------------------
    # init
    # ------------------------------------------------------------------
    parser_init = subparsers.add_parser(
        "init",
        help="Interactive wizard: scaffold a Mnemos vault",
    )
    parser_init.set_defaults(func=cmd_init)

    # ------------------------------------------------------------------
    # mine
    # ------------------------------------------------------------------
    parser_mine = subparsers.add_parser(
        "mine",
        help="Mine a file or directory and extract memory fragments",
    )
    parser_mine.add_argument(
        "path",
        help="File or directory to mine",
    )
    parser_mine.add_argument(
        "--llm",
        action="store_true",
        default=False,
        help="Use LLM-assisted extraction (requires anthropic package)",
    )
    parser_mine.add_argument(
        "--rebuild",
        action="store_true",
        default=False,
        help="Clear mine_log and re-mine all sources from scratch",
    )
    parser_mine.set_defaults(func=cmd_mine)

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------
    parser_search = subparsers.add_parser(
        "search",
        help="Semantic search over the memory palace",
    )
    parser_search.add_argument(
        "query",
        help="Search query",
    )
    parser_search.add_argument(
        "--wing",
        default=None,
        help="Filter results to this wing",
    )
    parser_search.add_argument(
        "--hall",
        default=None,
        help="Filter results to this hall (e.g. facts, decisions)",
    )
    parser_search.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of results (default: 5)",
    )
    parser_search.set_defaults(func=cmd_search)

    # ------------------------------------------------------------------
    # status
    # ------------------------------------------------------------------
    parser_status = subparsers.add_parser(
        "status",
        help="Show memory palace status",
    )
    parser_status.set_defaults(func=cmd_status)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------
    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
