"""Mnemos CLI — init, mine, search, status commands."""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from mnemos.config import load_config, HALLS_DEFAULT, WATCHER_IGNORE_DEFAULT


# ---------------------------------------------------------------------------
# install_hook — SessionStart hook management
# ---------------------------------------------------------------------------

HOOK_MARKER = "mnemos-auto-refine"


@dataclass
class HookInstallResult:
    status: str  # "installed" | "already-installed" | "uninstalled" | "not-found"
    settings_path: Path
    backup_path: Optional[Path] = None


def _utc_date_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def install_hook(vault: Path, uninstall: bool = False) -> HookInstallResult:
    """Install or uninstall the SessionStart auto-refine hook in ~/.claude/settings.json."""
    settings_path = Path.home() / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    backup: Optional[Path] = None
    if settings_path.exists():
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        if not uninstall:
            backup = settings_path.with_name(
                settings_path.name + f".bak-{_utc_date_str()}"
            )
            backup.write_text(settings_path.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        settings = {}

    hooks = settings.setdefault("hooks", {})
    sessionstart = hooks.setdefault("SessionStart", [])

    existing_idx: Optional[int] = None
    for i, entry in enumerate(sessionstart):
        if entry.get("_managed_by") == HOOK_MARKER:
            existing_idx = i
            break
        # Legacy detection: prior versions stored the marker as a shell comment
        # inside the command string. Match these too so uninstall / upgrade can
        # find them.
        for h in entry.get("hooks", []):
            if HOOK_MARKER in h.get("command", ""):
                existing_idx = i
                break
        if existing_idx is not None:
            break

    if uninstall:
        if existing_idx is None:
            return HookInstallResult(status="not-found", settings_path=settings_path)
        sessionstart.pop(existing_idx)
        if not sessionstart:
            hooks.pop("SessionStart", None)
        settings_path.write_text(
            json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return HookInstallResult(status="uninstalled", settings_path=settings_path)

    if existing_idx is not None:
        return HookInstallResult(status="already-installed", settings_path=settings_path)

    # Module invocation (`python -m mnemos.auto_refine_hook`) — no filesystem
    # path to ship; works for `pip install mnemos-dev` and `pip install -e .`
    # alike. Pre-3.10a we wrote the path to `<repo>/scripts/auto_refine_hook.py`
    # which only existed in dev installs.
    if os.name == "nt":
        if " " in str(vault):
            raise ValueError(
                f"vault path must not contain spaces (current CLI-arg based "
                f"invocation still needs a quote-free path). Got vault={vault!r}."
            )
        # Forward slashes survive Claude Code's Windows hook dispatcher (which
        # eats backslash escape sequences like \P, \m, \s, \a).
        vault_fs = str(vault).replace("\\", "/")
        full_cmd = f'python -m mnemos.auto_refine_hook --vault {vault_fs}'
    else:
        full_cmd = f'python -m mnemos.auto_refine_hook --vault "{vault}"'

    sessionstart.append({
        "matcher": "",
        "_managed_by": HOOK_MARKER,
        "hooks": [{
            "type": "command",
            "command": full_cmd,
            "timeout": 5,
        }],
    })
    settings_path.write_text(
        json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return HookInstallResult(status="installed", settings_path=settings_path, backup_path=backup)


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

    # From this point on, everything is locale-aware.
    from mnemos.i18n import t, resolve_lang
    from mnemos.config import MnemosConfig as _MC
    lang = resolve_lang(_MC(vault_path=vault_path, languages=languages))

    _print_intro(lang)

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

    # --- Onboarding: discover → present → choose → process ---
    _run_onboarding(cfg, lang=lang)

    # --- Hook activation: offer to install SessionStart hook ---
    _install_hook_prompt(lang=lang, vault=Path(cfg.vault_path))

    # --- Statusline: offer to wire up the progress snippet ---
    _install_statusline_prompt(lang=lang, vault=Path(cfg.vault_path))

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
# Onboarding helpers (Phase 1–5 of `mnemos init`)
# ---------------------------------------------------------------------------


def _print_intro(lang: str = "en") -> None:
    """Phase 1 — what Mnemos is and how it works."""
    from mnemos.i18n import t
    print(t("intro.body", lang))


def _run_onboarding(cfg, lang: str = "en") -> None:  # type: ignore[no-untyped-def]
    """Phase 2–4: discover sources, ask user, process per choice."""
    from mnemos import pending
    from mnemos.i18n import t
    from mnemos.onboarding import discover, format_estimate

    print(t("discovery.header", lang))
    sources = discover(cfg.vault_path)

    if not sources:
        print(t("discovery.empty", lang))
        return

    # Phase 2 report — per-source line stays format-string driven (data row, not prose).
    total_secs = 0.0
    for i, src in enumerate(sources, 1):
        print(
            f"  {i}. {src.id:<22} — {src.file_count} files  "
            f"({format_estimate(src.estimated_seconds)}, {src.classification})"
        )
        total_secs += src.estimated_seconds
    print(t("discovery.total_estimate", lang, estimate=format_estimate(total_secs)))

    # Phase 3 choice
    print(t("choice.options_header", lang))
    print(t("choice.option_a", lang))
    print(t("choice.option_s", lang))
    print(t("choice.option_l", lang))
    raw_choice = input(t("choice.prompt", lang)).strip().upper()
    while raw_choice not in {"A", "S", "L"}:
        raw_choice = input(t("choice.invalid", lang)).strip().upper()

    # Phase 4 process
    for src in sources:
        existing = pending.load(cfg.vault_path).get(src.id)
        if existing and existing.status == "done":
            print(t("outcome.skip_done", lang, sid=src.id))
            continue

        if raw_choice == "A":
            decision = "process"
        elif raw_choice == "L":
            decision = "later"
        else:  # S — ask per source
            decision = _ask_per_source(src, format_estimate(src.estimated_seconds), lang)

        _apply_decision(cfg, src, decision, lang=lang)


def _ask_per_source(src, estimate: str, lang: str = "en") -> str:  # type: ignore[no-untyped-def]
    """Selective-mode prompt for one source. Returns 'process' | 'later' | 'skip'."""
    from mnemos.i18n import t
    print(t("per_source.header", lang,
            sid=src.id, n=src.file_count, est=estimate, cls=src.classification))
    raw = input(t("per_source.prompt", lang)).strip().upper()
    while raw not in {"Y", "L", "S"}:
        raw = input(t("per_source.invalid", lang)).strip().upper()
    return {"Y": "process", "L": "later", "S": "skip"}[raw]


def _apply_decision(cfg, src, decision: str, lang: str = "en") -> None:  # type: ignore[no-untyped-def]
    """Carry out user decision for one source + record it in pending.json."""
    from mnemos import onboarding
    from mnemos.i18n import t

    common = dict(
        source_id=src.id, kind=src.kind,
        root_path=src.root_path, file_count=src.file_count,
    )

    if decision == "skip":
        onboarding.mark_skipped(cfg.vault_path, **common, last_action="skipped-during-init")
        print(t("outcome.skipped", lang, sid=src.id))
        return

    if decision == "later" or src.classification == "raw":
        # Raw sources always go to pending in 3.4a — refine skill is
        # user-driven (mnemos itself does not call any LLM API).
        last_action = (
            "awaiting-refine-skill"
            if src.classification == "raw"
            else "deferred-by-user"
        )
        onboarding.register_pending(cfg.vault_path, **common, last_action=last_action)
        if src.classification == "raw":
            print(t("outcome.raw_registered", lang,
                    sid=src.id, n=src.file_count, path=src.root_path))
        else:
            print(t("outcome.later", lang, sid=src.id))
        return

    # Curated source, process now
    _mine_and_record(cfg, src.id, src.kind, src.root_path, src.file_count,
                     "mined-during-init", lang=lang)


def _mine_and_record(cfg, source_id: str, kind: str, root_path: str,
                     file_count: int, last_action: str,
                     lang: str = "en") -> dict:  # type: ignore[no-untyped-def]
    """Shared mining flow: in-progress → handle_mine → done."""
    from mnemos import onboarding
    from mnemos.i18n import t
    from mnemos.server import MnemosApp

    onboarding.mark_in_progress(
        cfg.vault_path, source_id=source_id, kind=kind,
        root_path=root_path, file_count=file_count,
    )
    print(t("outcome.mining", lang, sid=source_id, n=file_count))

    with MnemosApp(cfg) as app:
        result = app.handle_mine(path=root_path, use_llm=cfg.use_llm)

    onboarding.mark_done(
        cfg.vault_path, source_id=source_id, kind=kind,
        root_path=root_path, file_count=file_count,
        processed=result.get("files_scanned", file_count),
        last_action=last_action,
    )
    print(t("outcome.done", lang,
            sid=source_id,
            scanned=result.get("files_scanned", 0),
            drawers=result.get("drawers_created", 0),
            entities=result.get("entities_found", 0)))
    return result


# ---------------------------------------------------------------------------
# Import command family
# ---------------------------------------------------------------------------


def cmd_import(args: argparse.Namespace) -> None:
    """Dispatch `mnemos import <kind>` to the right handler."""
    vault_path = _resolve_vault(args.vault)
    _require_vault(vault_path, "import")
    cfg = load_config(vault_path)

    handler = {
        "claude-code": _import_claude_code,
        "chatgpt": _import_chatgpt,
        "slack": _import_slack,
        "markdown": _import_markdown,
        "memory": _import_memory,
    }.get(args.import_kind)

    if handler is None:
        sys.exit(
            f"[mnemos import] Unknown source kind: {args.import_kind!r}.\n"
            "Available: claude-code, chatgpt, slack, markdown, memory."
        )

    handler(cfg, args)


def _import_claude_code(cfg, args: argparse.Namespace) -> None:  # type: ignore[no-untyped-def]
    """Register Claude Code JSONL transcripts as pending → user runs refine skill."""
    from mnemos import onboarding

    if args.projects_dir:
        projects = Path(args.projects_dir).expanduser().resolve()
    else:
        default = onboarding.default_claude_projects_dir()
        if default is None:
            sys.exit(
                "[mnemos import claude-code] Could not find ~/.claude/projects.\n"
                "Pass --projects-dir <path> explicitly."
            )
        projects = default

    if not projects.is_dir():
        sys.exit(f"[mnemos import claude-code] Not a directory: {projects}")

    jsonls = list(projects.rglob("*.jsonl"))
    if args.limit:
        jsonls = jsonls[: args.limit]

    if not jsonls:
        print(f"No .jsonl files under {projects}.")
        return

    onboarding.register_pending(
        cfg.vault_path, source_id="claude-code-jsonl", kind="raw-jsonl",
        root_path=str(projects), file_count=len(jsonls),
        last_action="awaiting-refine-skill",
    )
    print(
        f"Registered {len(jsonls)} JSONL transcripts under {projects}.\n"
        "Next step:\n"
        "  In a Claude Code session, run /mnemos-refine-transcripts to\n"
        "  convert these into Sessions/<YYYY-MM-DD>-<slug>.md notes,\n"
        "  then run `mnemos import markdown <vault>/Sessions` to mine them."
    )


def _import_single_file_export(cfg, args: argparse.Namespace,
                                source_id: str, kind: str) -> None:  # type: ignore[no-untyped-def]
    """Shared logic for ChatGPT / Slack JSON exports (single-file inputs)."""
    path = Path(args.path).expanduser().resolve()
    if not path.is_file():
        sys.exit(f"[mnemos import] Not a file: {path}")
    _mine_and_record(cfg, source_id, kind, str(path), 1, f"imported-via-{source_id}")


def _import_chatgpt(cfg, args: argparse.Namespace) -> None:  # type: ignore[no-untyped-def]
    _import_single_file_export(cfg, args, source_id="chatgpt-export", kind="raw-json")


def _import_slack(cfg, args: argparse.Namespace) -> None:  # type: ignore[no-untyped-def]
    _import_single_file_export(cfg, args, source_id="slack-export", kind="raw-json")


def _import_dir(cfg, args: argparse.Namespace,
                source_id: str, kind: str) -> None:  # type: ignore[no-untyped-def]
    """Shared logic for markdown / memory directory imports."""
    path = Path(args.path).expanduser().resolve()
    if not path.is_dir():
        sys.exit(f"[mnemos import] Not a directory: {path}")
    md_files = list(path.glob("*.md"))
    if not md_files:
        sys.exit(f"[mnemos import] No .md files in {path}")
    _mine_and_record(cfg, source_id, kind, str(path), len(md_files),
                     f"imported-via-{source_id}")


def _import_markdown(cfg, args: argparse.Namespace) -> None:  # type: ignore[no-untyped-def]
    _import_dir(cfg, args, source_id="markdown-import", kind="curated-md")


def _import_memory(cfg, args: argparse.Namespace) -> None:  # type: ignore[no-untyped-def]
    _import_dir(cfg, args, source_id="memory-import", kind="curated-md")


def _install_hook_prompt(lang: str = "en", vault: Path = Path(".")) -> None:
    """Phase 5 — ask the user to install the SessionStart auto-refine hook."""
    from mnemos.i18n import t

    answer = input(t("hook_install_prompt", lang)).strip().lower()
    yes_answers = {"", "y", "yes", "e", "evet"}
    if answer not in yes_answers:
        print(t("hook_install_declined", lang))
        return

    result = install_hook(vault=vault, uninstall=False)
    if result.status == "already-installed":
        print(t("hook_install_already", lang))
    else:
        print(t("hook_install_done", lang))


def _install_statusline_prompt(lang: str = "en", vault: Path = Path(".")) -> None:
    """Phase 5 extra — offer to install the statusline snippet."""
    from mnemos.i18n import t
    from mnemos.install_statusline import install_statusline

    answer = input(t("statusline_install_prompt", lang)).strip().lower()
    yes_answers = {"", "y", "yes", "e", "evet"}
    if answer not in yes_answers:
        print(t("statusline_install_declined", lang))
        return

    result = install_statusline(vault=vault, uninstall=False)
    if result.status == "already-installed":
        print(t("statusline_install_already", lang))
    else:
        print(t("statusline_install_done", lang))


# ---------------------------------------------------------------------------
# cmd_mine
# ---------------------------------------------------------------------------


def cmd_mine(args: argparse.Namespace) -> None:
    """Mine a file or directory and print results as JSON."""
    vault_path = _resolve_vault(args.vault)
    _require_vault(vault_path, "mine")

    cfg = load_config(vault_path)

    from mnemos.server import MnemosApp

    with MnemosApp(cfg) as app:
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
        meta = r.get("metadata") or {}
        wing = meta.get("wing", "?")
        hall = meta.get("hall", "?")
        text = r.get("text", "").strip()
        # Truncate long texts for readability
        preview = text[:200] + "..." if len(text) > 200 else text
        print(f"[{i}] score={score:.3f}  wing={wing}  hall={hall}")
        print(f"     {preview}")
        print()


# ---------------------------------------------------------------------------
# cmd_status
# ---------------------------------------------------------------------------


def cmd_migrate(args: argparse.Namespace) -> None:
    """Migrate the vault's vector backend (3.14b)."""
    vault_path = _resolve_vault(args.vault)
    _require_vault(vault_path, "migrate")

    cfg = load_config(vault_path)

    from mnemos.migrate import migrate as run_migrate

    if args.dry_run:
        result = run_migrate(cfg, new_backend=args.backend, dry_run=True)
    else:
        if cfg.search_backend != args.backend:
            print(
                f"Migrating {cfg.search_backend} → {args.backend}. "
                f"Rebuild may take several minutes. Do not Ctrl+C."
            )
        result = run_migrate(
            cfg,
            new_backend=args.backend,
            no_rebuild=args.no_rebuild,
        )

    _print_migration_result(result, cfg)


def _print_migration_result(result, cfg: "MnemosConfig") -> None:  # type: ignore[name-defined]
    """Render a MigrationResult in a human-readable block."""
    if result.status == "noop":
        print(f"Already on backend '{result.to_backend}'. Nothing to do.")
        return

    if result.status == "dry-run":
        plan = result.plan
        lo_min, hi_min = plan.estimate_minutes_range()
        src_list = ", ".join(f"{d}/" for d in plan.source_dirs) or "(none found)"
        print("Migration plan (dry-run, no files changed):")
        print(f"  From:         {plan.from_backend}")
        print(f"  To:           {plan.to_backend}")
        print(f"  Drawers now:  {plan.current_drawers}")
        print(f"  Source files: {plan.source_files} .md in {src_list}")
        if plan.current_drawers == 0:
            print("  Note:         current index is empty — rebuild will start from scratch.")
        elif plan.source_files == 0:
            print("  Warning:      no source .md files found under Sessions/, Topics/, memory/.")
            print("                Rebuild would produce an empty index. Pass --no-rebuild to")
            print("                update yaml only, or restore your source files before running.")
        print(f"  Time est.:    ~{lo_min}–{hi_min} minutes (based on 0.46 s/drawer ±30%)")
        return

    # migrated
    delta = result.drawers_after - result.drawers_before
    sign = "+" if delta >= 0 else ""
    print(f"Migrated {result.from_backend} → {result.to_backend}.")
    print(f"  Drawers: {result.drawers_before} → {result.drawers_after}  ({sign}{delta})")
    if result.backup_path:
        print(f"  Backup:  {result.backup_path}")
    if (
        result.drawers_before > 0
        and result.drawers_after < int(result.drawers_before * 0.8)
    ):
        print(
            f"  Warning: rebuild produced fewer drawers than before. "
            f"Missing source files? Backup preserved so you can restore."
        )


def _format_bytes(n: int) -> str:
    """Human-readable byte count: 1536 → '1.5 KB', 42_336_000 → '42.3 MB'."""
    if n < 1024:
        return f"{n} B"
    units = ["KB", "MB", "GB", "TB"]
    value = float(n)
    for unit in units:
        value /= 1024.0
        if value < 1024.0 or unit == units[-1]:
            return f"{value:.1f} {unit}"
    return f"{value:.1f} TB"


def cmd_status(args: argparse.Namespace) -> None:
    """Print memory palace status — human backend line + full JSON."""
    vault_path = _resolve_vault(args.vault)
    _require_vault(vault_path, "status")

    cfg = load_config(vault_path)

    from mnemos.server import MnemosApp

    app = MnemosApp(cfg)
    result = app.handle_status()

    # Human-readable backend summary line (3.14e)
    b = result.get("backend") or {}
    name = b.get("name") or "?"
    path_str: str
    raw_path = b.get("path")
    if raw_path:
        p = Path(raw_path)
        path_str = (p.name + "/") if p.is_dir() else p.name
    else:
        path_str = "in-memory"
    bytes_ = int(b.get("storage_bytes") or 0)
    size_str = _format_bytes(bytes_) if bytes_ else "empty"
    total = int(result.get("total_drawers") or 0)
    print(f"Backend: {name} ({path_str} · {total} drawers · {size_str})")
    print()
    print(json.dumps(result, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# cmd_benchmark
# ---------------------------------------------------------------------------


def cmd_install_hook(args: argparse.Namespace) -> None:
    """Install or uninstall the SessionStart auto-refine hook."""
    vault_path = _resolve_vault(args.vault)
    if not vault_path:
        vault_path = str(Path.cwd())

    result = install_hook(vault=Path(vault_path), uninstall=args.uninstall)
    print(f"{result.status}: {result.settings_path}")
    if result.backup_path:
        print(f"backup: {result.backup_path}")


def cmd_install_statusline(args: argparse.Namespace) -> None:
    """Install or uninstall the mnemos statusline snippet."""
    from mnemos.install_statusline import install_statusline

    vault_path = _resolve_vault(args.vault)
    if not vault_path:
        vault_path = str(Path.cwd())

    result = install_statusline(vault=Path(vault_path), uninstall=args.uninstall)
    print(f"{result.status}: {result.settings_path}")
    if result.script_path:
        print(f"script: {result.script_path}")
    if result.settings_backup_path:
        print(f"settings backup: {result.settings_backup_path}")
    if result.script_backup_path:
        print(f"script backup: {result.script_backup_path}")


def cmd_benchmark(args: argparse.Namespace) -> None:
    """Run a recall benchmark and print aggregated metrics as JSON."""
    if args.dataset != "longmemeval":
        sys.exit(f"[mnemos benchmark] Unknown dataset: {args.dataset!r}. Only 'longmemeval' is supported.")

    try:
        from benchmarks.longmemeval.runner import run_benchmark
    except ImportError as exc:
        sys.exit(
            f"[mnemos benchmark] Could not import benchmark module: {exc}\n"
            "Make sure you are running from the repository root."
        )

    result = run_benchmark(
        mode=args.mode,
        limit=args.limit or 0,
        subset=args.subset,
        split=args.split,
        use_llm=args.llm,
        verbose=True,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# main — argparse entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    # Ensure non-ASCII output (Turkish onboarding text, Unicode in vault paths)
    # works on Windows consoles that default to cp1252. No-op on Unix where
    # stdout is already UTF-8, and silent on older Pythons that lack the API.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

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
    # import — bring an external knowledge source into the palace
    # ------------------------------------------------------------------
    parser_import = subparsers.add_parser(
        "import",
        help="Import a knowledge source (claude-code / chatgpt / slack / markdown / memory)",
    )
    import_subs = parser_import.add_subparsers(
        dest="import_kind", metavar="<kind>", required=True,
    )

    p_cc = import_subs.add_parser(
        "claude-code",
        help="Register Claude Code JSONL transcripts (refine via skill afterward)",
    )
    p_cc.add_argument("--projects-dir", default=None,
                      help="Override ~/.claude/projects path")
    p_cc.add_argument("--limit", type=int, default=0,
                      help="Limit number of JSONLs to register (0 = all)")
    p_cc.set_defaults(func=cmd_import)

    p_chat = import_subs.add_parser("chatgpt", help="Mine a ChatGPT JSON export file")
    p_chat.add_argument("path", help="Path to the chatgpt export .json")
    p_chat.set_defaults(func=cmd_import)

    p_slack = import_subs.add_parser("slack", help="Mine a Slack JSON export file")
    p_slack.add_argument("path", help="Path to the slack export .json")
    p_slack.set_defaults(func=cmd_import)

    p_md = import_subs.add_parser("markdown", help="Mine a directory of curated .md files")
    p_md.add_argument("path", help="Directory containing .md files")
    p_md.set_defaults(func=cmd_import)

    p_mem = import_subs.add_parser(
        "memory", help="Mine a Claude memory export directory (.md files)",
    )
    p_mem.add_argument("path", help="Directory containing memory .md files")
    p_mem.set_defaults(func=cmd_import)

    # ------------------------------------------------------------------
    # install-hook
    # ------------------------------------------------------------------
    parser_install_hook = subparsers.add_parser(
        "install-hook",
        help="Install/uninstall the SessionStart auto-refine hook",
    )
    parser_install_hook.add_argument("--uninstall", action="store_true")
    parser_install_hook.set_defaults(func=cmd_install_hook)

    # ------------------------------------------------------------------
    # install-statusline
    # ------------------------------------------------------------------
    parser_install_statusline = subparsers.add_parser(
        "install-statusline",
        help="Install/uninstall the statusline snippet (shows auto-refine progress)",
    )
    parser_install_statusline.add_argument("--uninstall", action="store_true")
    parser_install_statusline.set_defaults(func=cmd_install_statusline)

    # ------------------------------------------------------------------
    # migrate
    # ------------------------------------------------------------------
    parser_migrate = subparsers.add_parser(
        "migrate",
        help="Switch vector backend (chromadb ↔ sqlite-vec) safely",
    )
    parser_migrate.add_argument(
        "--backend",
        required=True,
        choices=["chromadb", "sqlite-vec"],
        help="Target backend — the vault's mnemos.yaml will be updated and the index rebuilt.",
    )
    parser_migrate.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the migration plan (drawers, source files, time estimate) without changing anything.",
    )
    parser_migrate.add_argument(
        "--no-rebuild",
        action="store_true",
        help="Update yaml + back up old storage but skip the rebuild (advanced; you re-mine manually later).",
    )
    parser_migrate.set_defaults(func=cmd_migrate)

    # ------------------------------------------------------------------
    # benchmark
    # ------------------------------------------------------------------
    parser_bench = subparsers.add_parser(
        "benchmark",
        help="Run a recall benchmark (default: longmemeval)",
    )
    parser_bench.add_argument(
        "dataset",
        nargs="?",
        default="longmemeval",
        help="Benchmark dataset to run (default: longmemeval)",
    )
    parser_bench.add_argument(
        "--mode",
        choices=["raw-only", "mined-only", "combined", "filtered"],
        default="combined",
        help="Search collection mode (default: combined)",
    )
    parser_bench.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of questions to evaluate (default: 10; 0 = all)",
    )
    parser_bench.add_argument(
        "--subset",
        default="longmemeval_s",
        help="Dataset subset name (default: longmemeval_s)",
    )
    parser_bench.add_argument(
        "--split",
        default="test",
        help="Dataset split name (default: test)",
    )
    parser_bench.add_argument(
        "--llm",
        action="store_true",
        default=False,
        help="Enable LLM-assisted mining during benchmark",
    )
    parser_bench.set_defaults(func=cmd_benchmark)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------
    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(0)

    from mnemos.errors import BackendInitError

    try:
        args.func(args)
    except BackendInitError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
