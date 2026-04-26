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
from mnemos.i18n import resolve_lang, t


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


def _compute_global_progress(vault: Path, cfg) -> dict:
    """Walk the user's projects + vault Sessions + refine ledger to compute
    overall refinement progress: how many JSONLs passed the user-turn filter,
    how many produced Session notes, how many were SKIPed by the refine
    skill, and the resulting readiness percentage."""
    from mnemos.readiness import (
        count_eligible_jsonls,
        count_refined_sessions,
        compute_readiness_pct,
    )

    projects = Path.home() / ".claude" / "projects"
    eligible = count_eligible_jsonls(
        projects, min_user_turns=cfg.refine.min_user_turns
    )
    refined = count_refined_sessions(vault)

    ledger = Path.home() / ".claude/skills/mnemos-refine-transcripts/state/processed.tsv"
    skipped = 0
    if ledger.exists():
        try:
            with ledger.open("r", encoding="utf-8", errors="replace") as fh:
                for raw in fh:
                    parts = raw.rstrip("\r\n").split("\t")
                    if len(parts) >= 2 and parts[1] == "SKIP":
                        skipped += 1
        except OSError:
            pass

    return {
        "eligible": eligible,
        "refined": refined,
        "skipped": skipped,
        "pct": compute_readiness_pct(refined, eligible),
    }


def render_menu(vault: Path) -> str:
    cfg = load_config(str(vault))
    lang = resolve_lang(cfg)
    lines: list[str] = []
    lines.append("=" * 68)
    lines.append(t("settings.title", lang))
    lines.append(f"Vault: {vault}")
    lines.append("=" * 68)
    lines.append("")
    lines.append(t("settings.refine_section", lang))
    lines.append(_format_field_line(1, "JSONLs per session start", str(cfg.refine.per_session)))
    lines.append(_format_field_line(2, "Direction", cfg.refine.direction))
    lines.append(_format_field_line(3, "Min user turns (noise floor)", str(cfg.refine.min_user_turns)))
    lines.append("")
    lines.append(t("settings.briefing_section", lang))
    lines.append(_format_field_line(4, "Readiness gate (%)", str(cfg.briefing.readiness_pct)))
    lines.append(_format_field_line(5, "Show systemMessage display", str(cfg.briefing.show_systemmessage).lower()))
    lines.append(_format_field_line(6, "Enforce consistency check", str(cfg.briefing.enforce_consistency).lower()))
    lines.append("")
    lines.append(t("settings.identity_section", lang))
    lines.append(_format_field_line(7, "Bootstrap unlock threshold (%)", str(cfg.identity.bootstrap_threshold_pct)))
    lines.append(_format_field_line(8, "Auto-refresh", str(cfg.identity.auto_refresh).lower()))
    lines.append(_format_field_line(9, "Refresh session delta", str(cfg.identity.refresh_session_delta)))
    lines.append(_format_field_line(10, "Refresh min days", str(cfg.identity.refresh_min_days)))
    lines.append("")
    lines.append(t("settings.hooks_section", lang))
    lines.append(_format_hook_line(11, "auto-refine SessionStart", _check_hook_installed("mnemos-auto-refine")))
    lines.append(_format_hook_line(12, "recall-briefing SessionStart", _check_hook_installed("mnemos-recall-briefing")))
    lines.append(_format_hook_line(13, "session-end (NEW v1.1)", _check_hook_installed("mnemos-session-end")))
    lines.append(_format_hook_line(14, "statusline", False))
    lines.append("")
    lines.append(t("settings.backend_section", lang))
    lines.append(_format_field_line(15, "Search backend", cfg.search_backend))
    lines.append(_format_field_line(16, "Languages", str(cfg.languages)))
    lines.append(_format_field_line(17, "Recall mode", cfg.recall_mode))
    lines.append("")
    lines.append(t("settings.progress_section", lang))
    prog = _compute_global_progress(vault, cfg)
    lines.append(f"  Eligible JSONLs:        {prog['eligible']}")
    lines.append(
        f"  Refined to Sessions:    {prog['refined']}  ({prog['pct']:.1f}%)"
    )
    if prog["pct"] >= cfg.identity.bootstrap_threshold_pct:
        bootstrap_status = "[unlocked]"
    else:
        bootstrap_status = (
            f"[locked] need {cfg.identity.bootstrap_threshold_pct}%, "
            f"have {prog['pct']:.1f}%"
        )
    lines.append(f"  Identity bootstrap:     {bootstrap_status}")
    lines.append("  18) Per-cwd briefing readiness breakdown")
    lines.append("  19) Run identity bootstrap manually")
    lines.append("  20) Run identity refresh now")
    lines.append("")
    lines.append("  q) Quit")
    lines.append("=" * 68)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Validators (Task 9.2)
# ---------------------------------------------------------------------------


def validate_int(s: str, min_v: int, max_v: int) -> tuple[bool, int, str]:
    try:
        v = int(s)
    except ValueError:
        return False, 0, f"Not an integer: {s!r}"
    if v < min_v or v > max_v:
        return False, 0, f"Out of range [{min_v}, {max_v}]: {v}"
    return True, v, ""


def validate_bool(s: str) -> tuple[bool, bool, str]:
    s = s.strip().lower()
    if s in ("true", "t", "yes", "y", "1"):
        return True, True, ""
    if s in ("false", "f", "no", "n", "0"):
        return True, False, ""
    return False, False, f"Not a bool (true/false expected): {s!r}"


def validate_choice(s: str, choices: list[str]) -> tuple[bool, str, str]:
    if s in choices:
        return True, s, ""
    return False, "", f"Not in {choices}: {s!r}"


# ---------------------------------------------------------------------------
# Field application (Task 9.3)
# ---------------------------------------------------------------------------


# Menu number -> (config section, attribute). The "__direct__" sentinel
# routes to MnemosConfig itself for top-level fields like search_backend.
_FIELD_MAP: dict[int, tuple[str, str]] = {
    1: ("refine", "per_session"),
    2: ("refine", "direction"),
    3: ("refine", "min_user_turns"),
    4: ("briefing", "readiness_pct"),
    5: ("briefing", "show_systemmessage"),
    6: ("briefing", "enforce_consistency"),
    7: ("identity", "bootstrap_threshold_pct"),
    8: ("identity", "auto_refresh"),
    9: ("identity", "refresh_session_delta"),
    10: ("identity", "refresh_min_days"),
    15: ("__direct__", "search_backend"),
    17: ("__direct__", "recall_mode"),
}


def apply_field_change(cfg, field_num: int, value) -> None:
    """Apply a validated value to the appropriate cfg attribute by menu number."""
    if field_num not in _FIELD_MAP:
        raise ValueError(f"Field {field_num} not editable via apply_field_change")
    section, attr = _FIELD_MAP[field_num]
    if section == "__direct__":
        setattr(cfg, attr, value)
    else:
        setattr(getattr(cfg, section), attr, value)


# ---------------------------------------------------------------------------
# Per-cwd readiness breakdown (Task 9.5)
# ---------------------------------------------------------------------------


def format_per_cwd_breakdown(vault: Path) -> str:
    """Render a per-cwd readiness table for option 18 of the menu.

    Reads the cwd state file (written by recall_briefing.save_state) and
    computes per_cwd_readiness for each entry. Each row shows the cwd,
    refined/eligible counts, the percentage, and whether the briefing
    inject gate would unlock at the current cfg.briefing.readiness_pct.
    """
    from mnemos.readiness import per_cwd_readiness

    state_path = vault / ".mnemos-cwd-state.json"
    if not state_path.exists():
        return "No per-cwd state recorded yet."
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "State file unreadable."

    cfg = load_config(str(vault))
    projects_root = Path.home() / ".claude" / "projects"
    lines: list[str] = ["", "Per-cwd readiness:"]
    for slug, info in state.get("cwds", {}).items():
        cwd = info.get("cwd", "?")
        r = per_cwd_readiness(
            vault=vault,
            cwd=cwd,
            cwd_slug=slug,
            projects_root=projects_root,
            min_user_turns=cfg.refine.min_user_turns,
        )
        gate = "[inject]" if r["pct"] >= cfg.briefing.readiness_pct else "[silent]"
        lines.append(f"  {cwd}")
        lines.append(
            f"    refined {r['refined']}/{r['eligible']}  "
            f"({r['pct']:.1f}%)  {gate}"
        )
    return "\n".join(lines)
