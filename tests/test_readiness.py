"""Tests for mnemos.readiness — eligibility/refined/pct helpers."""
from pathlib import Path

from mnemos.readiness import (
    count_eligible_jsonls,
    count_refined_sessions,
    compute_readiness_pct,
)


def test_count_eligible_jsonls_filters_by_min_turns(tmp_path):
    projects = tmp_path / "projects"
    projects.mkdir()
    # 2-turn JSONL — below threshold
    (projects / "noise.jsonl").write_text(
        '{"type":"user","message":{"role":"user","content":"hi"}}\n' * 2,
        encoding="utf-8",
    )
    # 5-turn JSONL — eligible
    (projects / "real.jsonl").write_text(
        '{"type":"user","message":{"role":"user","content":"hi"}}\n' * 5,
        encoding="utf-8",
    )

    assert count_eligible_jsonls(projects, min_user_turns=3) == 1


def test_count_refined_sessions_counts_md_files(tmp_path):
    sessions = tmp_path / "Sessions"
    sessions.mkdir()
    (sessions / "2026-01-01-foo.md").write_text(
        "---\ndate: 2026-01-01\n---\n", encoding="utf-8"
    )
    (sessions / "2026-01-02-bar.md").write_text(
        "---\ndate: 2026-01-02\n---\n", encoding="utf-8"
    )
    assert count_refined_sessions(tmp_path) == 2


def test_compute_readiness_pct_basic(tmp_path):
    # 1 refined out of 4 eligible = 25%
    assert compute_readiness_pct(refined=1, eligible=4) == 25.0
    # Edge: zero eligible -> 100% (no work to do)
    assert compute_readiness_pct(refined=0, eligible=0) == 100.0
