"""Mnemos statusline installer.

Writes an idempotent shell snippet that renders the auto-refine hook's live
progress in the Claude Code chatbox footer. Two modes:

1. **Append mode** — `~/.claude/settings.json` already has a parseable
   `statusLine.command` pointing to a user-owned `.sh` or `.cmd` script.
   We append a fenced block to that script and leave `settings.json` untouched.

2. **Fresh mode** — no statusLine configured (or unparseable). We create
   `~/.claude/mnemos-statusline.{sh,cmd}` (platform-dependent), make it contain
   only our block, and point `settings.json`'s `statusLine` at it.

Both modes are idempotent: re-running detects the block via `STATUSLINE_MARKER`
and reports `already-installed`. `uninstall=True` removes the block (and, in
fresh mode, the owned script + the settings entry we added).
"""
from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


STATUSLINE_MARKER = "mnemos-auto-refine-statusline"

_BEGIN_RE = re.compile(
    rf"(?m)^[ \t]*(?:#|rem)[ \t]*---[ \t]*{re.escape(STATUSLINE_MARKER)}\b.*$"
)
_END_RE = re.compile(
    rf"(?m)^[ \t]*(?:#|rem)[ \t]*---[ \t]*end[ \t]+{re.escape(STATUSLINE_MARKER)}\b.*$"
)


@dataclass
class StatuslineInstallResult:
    status: str  # "installed" | "already-installed" | "uninstalled" | "not-found"
    settings_path: Path
    script_path: Optional[Path] = None
    settings_backup_path: Optional[Path] = None
    script_backup_path: Optional[Path] = None
    owned: bool = False  # True iff mnemos created the script file


def _utc_date_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _repo_snippet_path() -> Path:
    """Location of the shipped snippet source (source of truth for the block body)."""
    repo_root = Path(__file__).resolve().parent.parent
    name = "statusline_snippet.cmd" if os.name == "nt" else "statusline_snippet.sh"
    return repo_root / "scripts" / name


def _owned_script_path() -> Path:
    name = "mnemos-statusline.cmd" if os.name == "nt" else "mnemos-statusline.sh"
    return Path.home() / ".claude" / name


def _parse_existing_target(command: str) -> Optional[Path]:
    """Extract the script path from a statusLine.command we can safely append to.

    Supported shapes:
      - `bash <path>.sh` / `sh <path>.sh`
      - `<path>.sh` (direct)
      - `<path>.cmd` (direct, Windows)
    Quoted paths are unwrapped.
    """
    if not command:
        return None
    cmd = command.strip()
    # Strip a leading shell invoker (bash, sh) if present.
    m = re.match(r'^(?:bash|sh)\s+(.+)$', cmd)
    if m:
        cmd = m.group(1).strip()
    # Unwrap optional quotes.
    if (cmd.startswith('"') and cmd.endswith('"')) or (cmd.startswith("'") and cmd.endswith("'")):
        cmd = cmd[1:-1]
    path = Path(cmd)
    if path.suffix.lower() in (".sh", ".cmd") and path.exists():
        return path
    return None


def _build_block(vault: Path) -> str:
    """Return the text block to insert into the statusline script."""
    snippet = _repo_snippet_path().resolve()
    snippet_fs = str(snippet).replace("\\", "/")
    vault_fs = str(Path(vault).resolve()).replace("\\", "/")
    if os.name == "nt":
        return (
            f'rem --- {STATUSLINE_MARKER} (managed by mnemos install-statusline) ---\n'
            f'set "MNEMOS_VAULT={vault_fs}"\n'
            f'call "{snippet_fs}"\n'
            f'rem --- end {STATUSLINE_MARKER} ---\n'
        )
    return (
        f'# --- {STATUSLINE_MARKER} (managed by mnemos install-statusline) ---\n'
        f'export MNEMOS_VAULT="{vault_fs}"\n'
        f'source "{snippet_fs}"\n'
        f'# --- end {STATUSLINE_MARKER} ---\n'
    )


def _strip_block(body: str) -> str:
    """Remove the managed block (between begin/end markers) plus one trailing newline."""
    begin = _BEGIN_RE.search(body)
    end = _END_RE.search(body)
    if not begin or not end or end.start() < begin.start():
        return body
    # Include the newline following the end marker, if any.
    end_cut = end.end()
    if end_cut < len(body) and body[end_cut] == "\n":
        end_cut += 1
    # Also trim a blank separator line we may have inserted before the block.
    start_cut = begin.start()
    if start_cut > 0 and body[start_cut - 1] == "\n":
        # Do not eat into actual content — only the separator newline we added.
        pass
    return body[:start_cut] + body[end_cut:]


def _backup(path: Path) -> Path:
    backup = path.with_name(path.name + f".bak-{_utc_date_str()}")
    shutil.copy2(path, backup)
    return backup


def _read_settings(settings_path: Path) -> dict:
    if not settings_path.exists():
        return {}
    return json.loads(settings_path.read_text(encoding="utf-8"))


def _write_settings(settings_path: Path, settings: dict) -> None:
    settings_path.write_text(
        json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def install_statusline(vault: Path, uninstall: bool = False) -> StatuslineInstallResult:
    """Install or uninstall the mnemos statusline snippet."""
    settings_path = Path.home() / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings = _read_settings(settings_path)

    statusline_cfg = settings.get("statusLine") or {}
    existing_cmd = statusline_cfg.get("command", "") if isinstance(statusline_cfg, dict) else ""
    existing_target = _parse_existing_target(existing_cmd)

    owned_path = _owned_script_path()
    # We own the script iff settings points at our owned path (our convention).
    points_to_owned = existing_target is not None and existing_target.resolve() == owned_path.resolve() if existing_target else False

    # ---- Uninstall ----
    if uninstall:
        # Find the managed block in either the user's script or our owned script.
        target = existing_target if existing_target and _has_block(existing_target) else None
        if target is None and owned_path.exists() and _has_block(owned_path):
            target = owned_path
            points_to_owned = True

        if target is None:
            return StatuslineInstallResult(status="not-found", settings_path=settings_path)

        body = target.read_text(encoding="utf-8")
        new_body = _strip_block(body)

        if points_to_owned:
            # Fresh-mode cleanup: remove the owned script and the statusLine key.
            target.unlink()
            if "statusLine" in settings:
                del settings["statusLine"]
            _write_settings(settings_path, settings)
            return StatuslineInstallResult(
                status="uninstalled", settings_path=settings_path,
                script_path=target, owned=True,
            )
        else:
            # Append-mode cleanup: rewrite user's script without our block; leave settings alone.
            target.write_text(new_body, encoding="utf-8")
            return StatuslineInstallResult(
                status="uninstalled", settings_path=settings_path,
                script_path=target, owned=False,
            )

    # ---- Install ----
    # Decide target: user-owned script (append mode) or our owned script (fresh mode).
    if existing_target is not None and not points_to_owned:
        target = existing_target
        is_fresh = False
    else:
        target = owned_path
        is_fresh = True

    # Already installed?
    if target.exists() and _has_block(target):
        return StatuslineInstallResult(
            status="already-installed", settings_path=settings_path,
            script_path=target, owned=is_fresh,
        )

    # Back up what we are about to touch.
    settings_backup: Optional[Path] = None
    if settings_path.exists() and settings:
        settings_backup = _backup(settings_path)

    script_backup: Optional[Path] = None
    if target.exists() and target.stat().st_size > 0:
        script_backup = _backup(target)

    # Write/append the block.
    block = _build_block(vault)
    if target.exists():
        body = target.read_text(encoding="utf-8")
        if body and not body.endswith("\n"):
            body += "\n"
        new_body = body + "\n" + block
    else:
        # Fresh script — prepend a shebang on posix.
        header = "@echo off\n" if os.name == "nt" else "#!/usr/bin/env bash\n"
        new_body = header + block
    target.write_text(new_body, encoding="utf-8")
    if os.name != "nt" and is_fresh:
        target.chmod(0o755)

    # Update settings.json only in fresh mode.
    if is_fresh:
        target_fs = str(target.resolve()).replace("\\", "/")
        if os.name == "nt":
            command = target_fs
        else:
            command = f"bash {target_fs}"
        settings["statusLine"] = {"type": "command", "command": command}
        _write_settings(settings_path, settings)

    return StatuslineInstallResult(
        status="installed",
        settings_path=settings_path,
        script_path=target,
        settings_backup_path=settings_backup,
        script_backup_path=script_backup,
        owned=is_fresh,
    )


def _has_block(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        body = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False
    return bool(_BEGIN_RE.search(body) and _END_RE.search(body))
