"""Settings TUI — numbered CLI menu for unified v1.1 configuration.

The menu surfaces the v1.1 nested config sections (refine / briefing /
identity), pre-existing v1.0 toggles (search_backend, recall_mode,
languages), the install state of each managed hook, and the global
refinement progress so the user has a single screen for tuning Mnemos.

Edit loop lives in ``mnemos.cli.cmd_settings`` — this module only owns
rendering, validation, and config mutation helpers so the same logic is
reusable from non-CLI contexts (e.g. future TUI tests, init flow).
"""
from __future__ import annotations

import json
from pathlib import Path

from mnemos.config import load_config


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def _format_field_line(num: int, label: str, value: str, width: int = 40) -> str:
    label_padded = label.ljust(width, ".")
    return f" {num:>2}) {label_padded} {value}"


def _format_hook_line(num: int, name: str, installed: bool) -> str:
    label_padded = name.ljust(40, ".")
    status = "[installed]" if installed else "[not installed]"
    return f" {num:>2}) {label_padded} {status}"


def _check_hook_installed(managed_by: str) -> bool:
    settings = Path.home() / ".claude" / "settings.json"
    if not settings.exists():
        return False
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    for ev in ("SessionStart", "SessionEnd"):
        for entry in data.get("hooks", {}).get(ev, []):
            if entry.get("_managed_by") == managed_by:
                return True
    return False


def render_menu(vault: Path) -> str:
    cfg = load_config(str(vault))
    lines: list[str] = []
    lines.append("=" * 68)
    lines.append("Mnemos Settings")
    lines.append(f"Vault: {vault}")
    lines.append("=" * 68)
    lines.append("")
    lines.append("Refine pipeline:")
    lines.append(_format_field_line(1, "JSONLs per session start", str(cfg.refine.per_session)))
    lines.append(_format_field_line(2, "Direction", cfg.refine.direction))
    lines.append(_format_field_line(3, "Min user turns (noise floor)", str(cfg.refine.min_user_turns)))
    lines.append("")
    lines.append("Briefing:")
    lines.append(_format_field_line(4, "Readiness gate (%)", str(cfg.briefing.readiness_pct)))
    lines.append(_format_field_line(5, "Show systemMessage display", str(cfg.briefing.show_systemmessage).lower()))
    lines.append(_format_field_line(6, "Enforce consistency check", str(cfg.briefing.enforce_consistency).lower()))
    lines.append("")
    lines.append("Identity:")
    lines.append(_format_field_line(7, "Bootstrap unlock threshold (%)", str(cfg.identity.bootstrap_threshold_pct)))
    lines.append(_format_field_line(8, "Auto-refresh", str(cfg.identity.auto_refresh).lower()))
    lines.append(_format_field_line(9, "Refresh session delta", str(cfg.identity.refresh_session_delta)))
    lines.append(_format_field_line(10, "Refresh min days", str(cfg.identity.refresh_min_days)))
    lines.append("")
    lines.append("Hooks (settings.json managed):")
    lines.append(_format_hook_line(11, "auto-refine SessionStart", _check_hook_installed("mnemos-auto-refine")))
    lines.append(_format_hook_line(12, "recall-briefing SessionStart", _check_hook_installed("mnemos-recall-briefing")))
    lines.append(_format_hook_line(13, "session-end (NEW v1.1)", _check_hook_installed("mnemos-session-end")))
    lines.append(_format_hook_line(14, "statusline", False))
    lines.append("")
    lines.append("Backend & locale:")
    lines.append(_format_field_line(15, "Search backend", cfg.search_backend))
    lines.append(_format_field_line(16, "Languages", str(cfg.languages)))
    lines.append(_format_field_line(17, "Recall mode", cfg.recall_mode))
    lines.append("")
    lines.append("--- Refinement Progress ---")
    lines.append("  Eligible JSONLs:        ?")
    lines.append("  Refined to Sessions:    ?")
    lines.append("  18) Per-cwd briefing readiness breakdown")
    lines.append("  19) Run identity bootstrap manually")
    lines.append("  20) Run identity refresh now")
    lines.append("")
    lines.append("  q) Quit")
    lines.append("=" * 68)
    return "\n".join(lines)
