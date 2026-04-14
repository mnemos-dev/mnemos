"""One-shot: mine Claude Code memory/ files into Mnemos with explicit wings.

Each memory file is mapped to a specific wing based on its content (decided
in-session, not by parent directory). The mapping is baked in below.
Originals under ~/.claude/projects/ are never modified — read-only source.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mnemos.config import load_config  # noqa: E402
from mnemos.server import MnemosApp  # noqa: E402

VAULT = Path(r"C:\Users\tugrademirors\OneDrive\Masaüstü\kasamd")
PROJECTS = Path.home() / ".claude" / "projects"

# Content-based mapping: file (relative to PROJECTS) -> wing
MAPPING: list[tuple[str, str]] = [
    # -- ProcureTrack (10) --
    ("C--Projeler-Sat-n-Alma/memory/feedback_approach.md", "ProcureTrack"),
    ("C--Projeler-Sat-n-Alma/memory/project_procuretrack_rebuild.md", "ProcureTrack"),
    ("C--Projeler-Sat-n-Alma/memory/reference_design_docs.md", "ProcureTrack"),
    ("C--Projeler-Sat-n-Alma-procuretrack/memory/feedback_ai_parse.md", "ProcureTrack"),
    ("C--Projeler-Sat-n-Alma-procuretrack/memory/feedback_debug_cleanup.md", "ProcureTrack"),
    ("C--Projeler-Sat-n-Alma-procuretrack/memory/feedback_delete_only_db.md", "ProcureTrack"),
    ("C--Projeler-Sat-n-Alma-procuretrack/memory/feedback_iterative_testing.md", "ProcureTrack"),
    ("C--Projeler-Sat-n-Alma-procuretrack/memory/project_advisor_strategy.md", "ProcureTrack"),
    ("C--Projeler-Sat-n-Alma-procuretrack/memory/project_current_status.md", "ProcureTrack"),
    ("C--Projeler-Sat-n-Alma-procuretrack/memory/reference_github_repo.md", "ProcureTrack"),
    ("C--Projeler-Sat-n-Alma-procuretrack/memory/reference_memoriki.md", "ProcureTrack"),

    # -- General (15) --
    ("C--Projeler/memory/project_map.md", "General"),
    ("C--Projeler/memory/security_audit.md", "General"),
    ("C--Projeler/memory/user_profile.md", "General"),
    ("C--Projeler-Sat-n-Alma/memory/user_tugra.md", "General"),
    ("C--Projeler-Sat-n-Alma-procuretrack/memory/user_profile.md", "General"),
    ("C--Users-tugrademirors--claude-projects/memory/feedback_no_questions.md", "General"),
    ("C--Users-tugrademirors--claude-projects/memory/feedback_quarantine.md", "General"),
    ("C--Users-tugrademirors-OneDrive-Masa-st-/memory/feedback_outlook_classic.md", "General"),
    ("C--Users-tugrademirors-OneDrive-Masa-st-/memory/user_profile.md", "General"),
    ("C--Users-tugrademirors-OneDrive-Masa-st--Claude--al--ma-Dosyas-/memory/feedback_google_over_openai.md", "General"),
    ("C--Users-tugrademirors-OneDrive-Masa-st--Claude--al--ma-Dosyas-/memory/user_profile.md", "General"),

    # -- Claude (2) --
    ("C--Projeler/memory/dev_environment.md", "Claude"),
    ("C--Projeler-Sat-n-Alma-procuretrack/memory/feedback_model_ids.md", "Claude"),

    # -- Mnemos (1) --
    ("C--Projeler/memory/project_mnemos.md", "Mnemos"),

    # -- LightRAG-PO-Arsivi (1) --
    ("C--Users-tugrademirors-OneDrive-Masa-st--Claude--al--ma-Dosyas-/memory/project_tavuk_vector_db.md", "LightRAG-PO-Arsivi"),

    # -- GYP (1) --
    ("C--Users-tugrademirors-OneDrive-Masa-st-/memory/reference_gyp_drilling_reports.md", "GYP"),
]


def main() -> None:
    cfg = load_config(str(VAULT))
    missing = [rel for rel, _ in MAPPING if not (PROJECTS / rel).is_file()]
    if missing:
        print("ERROR: missing source files:")
        for m in missing:
            print(f"  {m}")
        sys.exit(1)

    print(f"Mining {len(MAPPING)} memory file(s) with explicit wings...\n")
    by_wing: dict[str, int] = {}

    with MnemosApp(cfg) as app:
        for rel_path, wing in MAPPING:
            src = PROJECTS / rel_path
            result = app.handle_mine(
                path=str(src), external=True, wing_override=wing,
            )
            drawers = result.get("drawers_created", 0)
            by_wing[wing] = by_wing.get(wing, 0) + drawers
            status = "+" if drawers else " "
            print(f"  {status} [{wing:<22}] {drawers:>3} drawer(s)  {Path(rel_path).name}")

        stats = app.handle_status()

    print()
    print("Per-wing from this run:")
    for wing, n in sorted(by_wing.items(), key=lambda kv: -kv[1]):
        print(f"  {wing:<22} {n:>3}")
    print()
    print("Full vault status:")
    print(f"  total drawers: {stats['total_drawers']}")
    for wing, n in sorted(stats["wings_detail"].items(), key=lambda kv: -kv[1]):
        print(f"    {wing:<22} {n:>3}")


if __name__ == "__main__":
    main()
