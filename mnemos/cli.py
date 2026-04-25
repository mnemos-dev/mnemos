"""Mnemos CLI — init, search, status, install-hook commands.

v1.0 narrative-first pivot removed the mining subcommands (``mine``,
``catch-up``, ``migrate``, ``processing-log``) and the entire ``import``
command family (``claude-code``, ``chatgpt``, ``slack``, ``markdown``,
``memory``). They are pre-dispatched in :func:`main` BEFORE argparse so any
flags the user types (e.g. ``mnemos mine --rebuild`` or ``mnemos import
chatgpt /tmp/x.json``) are slurped into a friendly "removed in v1.0"
message instead of producing argparse "unrecognized arguments" errors.
See :data:`LEGACY_REMOVED`, :data:`LEGACY_IMPORT_KINDS`, and
:func:`cmd_removed`.
"""
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

    # --- Backend (v0.3.1 task 3.14a) ---
    # Skip the prompt when an existing yaml already pins a backend — we
    # don't overwrite previously-set choices on re-run.
    existing_backend: Optional[str] = None
    yaml_path_check = vault_dir / "mnemos.yaml"
    if yaml_path_check.exists():
        try:
            prev = yaml.safe_load(yaml_path_check.read_text(encoding="utf-8")) or {}
            if isinstance(prev, dict) and prev.get("search_backend"):
                existing_backend = str(prev["search_backend"])
        except Exception:
            existing_backend = None

    if existing_backend:
        print(f"  Keeping existing backend: {existing_backend}")
        search_backend = existing_backend
    else:
        search_backend = _ask_backend_choice(lang=lang)

    # --- Build config ---
    config_data: dict = {
        "vault_path": vault_path,
        "languages": languages,
        "use_llm": use_llm,
        "search_backend": search_backend,
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

    # --- Create vault structure ---
    # v1.0: mnemos.palace was removed; we just ensure the canonical
    # directories exist (Sessions/ for refined transcripts, Mnemos/ for
    # the identity placeholder hierarchy, plus the runtime data dirs that
    # config.py promises). Task 27 (mnemos init v2) will redesign this.
    from mnemos.config import MnemosConfig

    cfg = MnemosConfig(
        vault_path=vault_path,
        languages=languages,
        use_llm=use_llm,
        search_backend=search_backend,
    )
    cfg.palace_dir.mkdir(parents=True, exist_ok=True)
    (Path(cfg.vault_path) / "Sessions").mkdir(parents=True, exist_ok=True)
    cfg.identity_full_path.mkdir(parents=True, exist_ok=True)
    # _recycled/ is the canonical soft-delete target documented in CLAUDE.md
    # (see "Mimari hatırlatıcılar" — Sessions notes are moved here instead of
    # being deleted; the watcher then cleans the index).
    cfg.recycled_full_path.mkdir(parents=True, exist_ok=True)
    print(f"  Created vault structure at: {cfg.palace_dir}")

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

    # --- Recall-briefing hook: offer to install + flip recall_mode to skill ---
    _install_recall_hook_prompt(lang=lang, vault=Path(cfg.vault_path))

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


def _resolve_backend_hint(lang: str = "en") -> Optional[str]:
    """Platform-aware extra copy for the backend prompt (v0.3.1 task 3.14a).

    On Windows + Python 3.14 we've seen fewer HNSW flush issues with
    sqlite-vec than ChromaDB, so it's worth a gentle nudge. On every
    other platform we stay neutral and return None — the main prompt
    copy is enough.
    """
    if sys.platform != "win32":
        return None
    if sys.version_info < (3, 14):
        return None
    from mnemos.i18n import t
    return t("backend.hint_windows_py314", lang)


def _ask_backend_choice(lang: str = "en") -> str:
    """Interactive picker for `search_backend` (v0.3.1 task 3.14a).

    Returns ``"chromadb"`` or ``"sqlite-vec"``. Bare Enter keeps the
    legacy default (ChromaDB) so existing muscle memory isn't broken.
    """
    from mnemos.i18n import t

    print(t("backend.prompt_header", lang))
    print(t("backend.option_c", lang))
    print(t("backend.option_s", lang))
    hint = _resolve_backend_hint(lang)
    if hint:
        print(hint)
    print()

    prompt = t("backend.prompt", lang)
    invalid = t("backend.invalid", lang)
    while True:
        raw = input(prompt).strip().lower()
        if raw in ("", "c", "chromadb"):
            print(t("backend.chose_chromadb", lang))
            return "chromadb"
        if raw in ("s", "sqlite-vec", "sqlite_vec", "sqlitevec"):
            print(t("backend.chose_sqlite", lang))
            return "sqlite-vec"
        prompt = invalid


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
    """Carry out user decision for one source + record it in pending.json.

    v1.0: the "curated source, process now" branch used to call
    ``_mine_and_record`` which routed through ``MnemosApp.handle_mine``.
    With mining gone, curated sources are now registered as ``pending``
    just like deferred sources — Task 27 (``mnemos init`` v2) will redesign
    onboarding around the Sessions paradigm.
    """
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

    # Curated source — v1.0: register as pending (mining is gone). Task 27
    # will replace this with a Sessions-aware onboarding flow.
    onboarding.register_pending(
        cfg.vault_path, **common, last_action="awaiting-v1-onboarding",
    )
    print(t("outcome.later", lang, sid=src.id))


# ---------------------------------------------------------------------------
# Import command family — REMOVED in v1.0
# ---------------------------------------------------------------------------
#
# ``mnemos import <kind>`` was the entry point for funnelling external sources
# (ChatGPT/Slack JSON exports, curated markdown directories, Claude memory
# dirs) into the palace via ``MnemosApp.handle_mine``. The mining/drawer
# paradigm is gone in v1.0, so all four kinds are pre-dispatched as
# ``cmd_removed`` in :func:`main` (see :data:`LEGACY_IMPORT_KINDS`).
# v1.x may re-implement them on the Sessions paradigm.


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


def _install_recall_hook_prompt(lang: str = "en", vault: Path = Path(".")) -> None:
    """Phase 5 extra — offer to install the recall-briefing SessionStart hook.

    On accept, installs the hook into ~/.claude/settings.json AND flips
    `recall_mode: skill` in the vault's mnemos.yaml so the MCP instructions
    and the hook activate together.
    """
    from mnemos.i18n import t
    from mnemos.recall_briefing import install_recall_hook

    answer = input(t("recall_hook_install_prompt", lang) + " ").strip().lower()
    yes_answers = {"", "y", "yes", "e", "evet"}
    if answer not in yes_answers:
        print(t("recall_hook_install_declined", lang))
        return

    result = install_recall_hook(vault=vault, uninstall=False)
    print(f"  {result.status}: {result.settings_path}")

    # Flip recall_mode in mnemos.yaml to "skill" if not already set.
    yaml_path = vault / "mnemos.yaml"
    if yaml_path.exists():
        text = yaml_path.read_text(encoding="utf-8")
        if not any(line.strip().startswith("recall_mode:") for line in text.splitlines()):
            if not text.endswith("\n"):
                text += "\n"
            text += "recall_mode: skill\n"
            yaml_path.write_text(text, encoding="utf-8")

    print(t("recall_hook_install_done", lang))


# ---------------------------------------------------------------------------
# Removed-command shim — friendly error for v1.0-deleted subcommands.
# ---------------------------------------------------------------------------


# Legacy top-level subcommands removed by the v1.0 narrative-first pivot.
# Pre-dispatched in :func:`main` BEFORE argparse so trailing flags (e.g.
# ``mnemos mine --rebuild``) don't trigger argparse "unrecognized arguments"
# errors. See Issue C1 in the Task 4 review.
LEGACY_REMOVED = frozenset({"mine", "pilot", "migrate", "catch-up", "processing-log"})

# v1.0: every kind of ``mnemos import`` was retired alongside the mining
# pipeline that backed it. ``claude-code`` already had its own pre-dispatch
# branch (it pointed users at the refine skill); the remaining four kinds
# (``chatgpt``, ``slack``, ``markdown``, ``memory``) all funnelled through
# ``MnemosApp.handle_mine`` and are now pre-dispatched the same way.
LEGACY_IMPORT_KINDS = frozenset({"chatgpt", "slack", "markdown", "memory"})


def cmd_removed(command_name: str, remaining_args: list[str] | None = None) -> int:
    """Print a friendly removal message for a v1.0-removed (sub)command.

    Returns exit code 2 (so :func:`main` can return it directly).
    """
    _ = remaining_args  # captured for future telemetry; intentionally unused
    msg = (
        f"Error: `mnemos {command_name}` was removed in v1.0.\n"
        f"The mining/drawer paradigm is gone — Sessions/<date>-<slug>.md is\n"
        f"now the canonical memory unit. See\n"
        f"https://github.com/mnemos-dev/mnemos/tree/legacy/atomic-paradigm\n"
        f"for the previous paradigm."
    )
    if command_name == "import claude-code":
        msg += (
            "\nUse the /mnemos-refine-transcripts skill to convert Claude Code"
            "\nJSONLs to Sessions notes."
        )
    elif command_name.startswith("import "):
        kind = command_name.split(" ", 1)[1]
        msg += (
            f"\nv1.x may re-implement `import {kind}` on the Sessions"
            "\nparadigm; for now there is no replacement command."
        )
    print(msg, file=sys.stderr)
    return 2


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


def cmd_install_recall_hook(args: argparse.Namespace) -> None:
    """Install or uninstall the SessionStart recall-briefing hook."""
    from mnemos.recall_briefing import install_recall_hook

    vault_path = _resolve_vault(args.vault)
    if not vault_path:
        vault_path = str(Path.cwd())

    result = install_recall_hook(vault=Path(vault_path), uninstall=args.uninstall)
    print(f"{result.status}: {result.settings_path}")


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


def cmd_identity(args: argparse.Namespace) -> int:
    """Dispatch ``mnemos identity {bootstrap,refresh,rollback,show}``.

    All sub-actions surface :class:`mnemos.identity.IdentityError` as a
    friendly stderr message + exit code 1, matching the rest of the CLI's
    UX (see ``BackendInitError`` handling in :func:`main`).
    """
    from mnemos.identity import bootstrap, refresh, rollback, show, IdentityError

    vault = Path(args.vault) if args.vault else _resolve_vault_from_yaml()
    try:
        if args.identity_action == "bootstrap":
            path = bootstrap(vault, model=args.model)
            print(f"Identity layer created: {path}")
        elif args.identity_action == "refresh":
            if args.check:
                _print_refresh_trigger_status(vault)
                return 0
            result = refresh(vault, force=args.force, model=args.model)
            if result is None:
                print("Refresh skipped: trigger conditions not met (use --force to override).")
            else:
                print(f"Identity layer refreshed: {result}")
        elif args.identity_action == "rollback":
            if not args.yes:
                _confirm_rollback(vault, args.target)
            path = rollback(vault, target=args.target, confirm=True)
            print(f"Restored: {path}")
        elif args.identity_action == "show":
            print(show(vault))
        else:
            # No subcommand → print help
            print("Usage: mnemos identity {bootstrap,refresh,rollback,show}", file=sys.stderr)
            return 1
    except IdentityError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_reindex(args: argparse.Namespace) -> int:
    """Rebuild the vector index from ``Sessions/`` (optionally switching backend).

    Surfaces :class:`mnemos.reindex.ReindexError` as a friendly stderr
    message + exit code 1, matching the rest of the CLI's error UX.
    """
    from mnemos.reindex import reindex, ReindexError

    vault = Path(args.vault) if args.vault else _resolve_vault_from_yaml()
    try:
        result = reindex(vault, backend=args.backend, no_backup=args.no_backup)
    except ReindexError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Indexed {result['session_count']} sessions on {result['backend']}.")
    if result["backup_path"]:
        print(f"Backup: {result['backup_path']}")
    return 0


def _resolve_vault_from_yaml() -> Path:
    """Find mnemos.yaml in cwd or vault env var; return its ``vault:`` path.

    Falls back to ``MNEMOS_VAULT`` env var (looking for ``<env>/mnemos.yaml``).
    Exits with a friendly message if no yaml is locatable so identity
    subcommands degrade gracefully when the user forgot ``--vault``.
    """
    yaml_path = Path.cwd() / "mnemos.yaml"
    if not yaml_path.exists():
        env_vault = os.environ.get("MNEMOS_VAULT")
        if env_vault:
            yaml_path = Path(env_vault) / "mnemos.yaml"
    if not yaml_path.exists():
        print("Error: no mnemos.yaml in cwd; pass --vault explicitly", file=sys.stderr)
        sys.exit(1)
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    # Support both `vault:` (test fixtures, simple yaml) and `vault_path:`
    # (the canonical key written by `mnemos init`).
    vault_value = data.get("vault") or data.get("vault_path")
    if not vault_value:
        print(f"Error: mnemos.yaml at {yaml_path} has no `vault` or `vault_path`", file=sys.stderr)
        sys.exit(1)
    return Path(vault_value)


def _print_refresh_trigger_status(vault: Path) -> None:
    """Dry-run: show whether refresh trigger conditions would fire."""
    from mnemos.identity import _parse_frontmatter, _has_identity_relevant_new_tags
    identity_path = vault / "_identity" / "L0-identity.md"
    if not identity_path.exists():
        print("Trigger: no identity bootstrapped")
        return
    existing = identity_path.read_text(encoding="utf-8")
    fm = _parse_frontmatter(existing)
    last_count = int(fm.get("session_count_at_refresh", 0))
    sessions = sorted((vault / "Sessions").glob("*.md"), key=lambda p: p.name)
    new_count = len(sessions) - last_count
    quantity_ok = new_count >= 10
    relevance_ok = (
        _has_identity_relevant_new_tags(existing, sessions[last_count:])
        if quantity_ok
        else False
    )
    print(f"Quantity gate: {new_count} new sessions ({'OK' if quantity_ok else 'NEED >=10'})")
    print(f"Relevance gate: {'OK' if relevance_ok else 'no new entities'}")
    print(f"Would fire: {quantity_ok and relevance_ok}")


def _confirm_rollback(vault: Path, target: Optional[str]) -> None:
    """Show preview and prompt y/n. Raises IdentityError on n."""
    from mnemos.identity import IdentityError
    identity_dir = vault / "_identity"
    baks = sorted(identity_dir.glob("L0-identity.md.bak-*"))
    if not baks:
        raise IdentityError(f"no backup snapshots in {identity_dir}")
    chosen = (
        baks[-1] if target is None
        else next((b for b in baks if b.name.endswith(target)), None)
    )
    if chosen is None:
        raise IdentityError(f"no backup matching {target}")
    print(f"Will restore from: {chosen.name}")
    answer = input("Continue? [y/N] ").strip().lower()
    if answer != "y":
        raise IdentityError("rollback canceled by user")


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


def main(argv: list[str] | None = None) -> int:
    # Ensure non-ASCII output (Turkish onboarding text, Unicode in vault paths)
    # works on Windows consoles that default to cp1252. No-op on Unix where
    # stdout is already UTF-8, and silent on older Pythons that lack the API.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    argv = list(argv) if argv is not None else sys.argv[1:]

    # Pre-dispatch v1.0-removed legacy commands BEFORE argparse so any
    # ``--``-prefixed flags get a friendly migration nudge instead of
    # argparse's "unrecognized arguments" error (Python issue #17050 means
    # argparse.REMAINDER cannot reliably slurp `--flag` tokens).
    if argv and argv[0] in LEGACY_REMOVED:
        return cmd_removed(argv[0], argv[1:])
    # ``mnemos import <kind>`` — every kind was retired in v1.0. Pre-dispatch
    # before argparse so flags like ``--projects-dir`` don't trip argparse.
    if len(argv) >= 2 and argv[0] == "import":
        if argv[1] == "claude-code":
            return cmd_removed("import claude-code", argv[2:])
        if argv[1] in LEGACY_IMPORT_KINDS:
            return cmd_removed(f"import {argv[1]}", argv[2:])
    # Bare ``mnemos import`` (no kind) — redirect to the same friendly message.
    if len(argv) == 1 and argv[0] == "import":
        return cmd_removed("import", [])

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
    # mine / pilot / migrate / catch-up / processing-log — REMOVED in v1.0
    # ------------------------------------------------------------------
    # Pre-dispatched by `main()` before `parse_args()` — see LEGACY_REMOVED.
    # Registering them as argparse subparsers with REMAINDER does NOT work
    # for `--`-prefixed flags (Python issue #17050), which defeats the
    # migration nudge. So they are simply not registered with argparse.

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
    # pilot — REMOVED in v1.0 (pre-dispatched by `main()`).
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # import — REMOVED in v1.0 (every kind: claude-code / chatgpt / slack /
    # markdown / memory). All variants are pre-dispatched by `main()` so any
    # flags (e.g. ``--projects-dir``, file paths) get the friendly removal
    # message instead of an argparse error. Not registered as a subparser.
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
    # install-recall-hook
    # ------------------------------------------------------------------
    parser_install_recall_hook = subparsers.add_parser(
        "install-recall-hook",
        help="Install the SessionStart recall-briefing hook in ~/.claude/settings.json",
    )
    parser_install_recall_hook.add_argument("--vault")
    parser_install_recall_hook.add_argument("--uninstall", action="store_true")
    parser_install_recall_hook.set_defaults(func=cmd_install_recall_hook)

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
    # identity — bootstrap / refresh / rollback / show (v1.0 Identity Layer)
    # ------------------------------------------------------------------
    sub_identity = subparsers.add_parser("identity", help="Manage Identity Layer")
    identity_actions = sub_identity.add_subparsers(dest="identity_action")

    p_bootstrap = identity_actions.add_parser(
        "bootstrap", help="Generate L0-identity.md from all Sessions"
    )
    p_bootstrap.add_argument("--vault", help="Vault path (default: from mnemos.yaml)")
    p_bootstrap.add_argument("--model", default="sonnet", choices=["sonnet", "opus"])

    p_refresh = identity_actions.add_parser("refresh", help="Incremental update")
    p_refresh.add_argument("--vault")
    p_refresh.add_argument("--force", action="store_true", help="Bypass trigger conditions")
    p_refresh.add_argument("--check", action="store_true", help="Dry-run trigger evaluation")
    p_refresh.add_argument("--model", default="sonnet", choices=["sonnet", "opus"])

    p_rollback = identity_actions.add_parser("rollback", help="Restore from .bak snapshot")
    p_rollback.add_argument("--vault")
    p_rollback.add_argument("target", nargs="?", help="Snapshot suffix (default: latest)")
    p_rollback.add_argument("--yes", action="store_true", help="Skip confirmation")

    p_show = identity_actions.add_parser("show", help="Print current Identity Layer")
    p_show.add_argument("--vault")
    # Dispatch is special-cased in `main()` below — `cmd_identity` returns
    # an int so we can't slot it into the generic `args.func(args)` flow.

    # ------------------------------------------------------------------
    # reindex — rebuild vector index from Sessions (v1.0 backend switch +
    # recovery; replaces the removed ``migrate`` subcommand).
    # ------------------------------------------------------------------
    sub_reindex = subparsers.add_parser(
        "reindex", help="Rebuild vector index from Sessions"
    )
    sub_reindex.add_argument(
        "--backend",
        choices=["chromadb", "sqlite-vec"],
        help="Switch search backend before rebuilding",
    )
    sub_reindex.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backup of existing on-disk index",
    )
    sub_reindex.add_argument(
        "--vault", help="Vault path (default: from mnemos.yaml in cwd)"
    )
    # Dispatch is special-cased in `main()` below — `cmd_reindex` returns
    # an int so we can't slot it into the generic `args.func(args)` flow.

    # ------------------------------------------------------------------
    # migrate / catch-up — REMOVED in v1.0 (pre-dispatched by `main()`).
    # ------------------------------------------------------------------

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
    args = parser.parse_args(argv)

    # Special-case: identity returns an int directly (not via args.func).
    if getattr(args, "command", None) == "identity":
        return cmd_identity(args)

    # Special-case: reindex also returns an int directly.
    if getattr(args, "command", None) == "reindex":
        return cmd_reindex(args)

    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    from mnemos.errors import BackendInitError

    try:
        args.func(args)
    except BackendInitError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
