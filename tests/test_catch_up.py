from pathlib import Path


def test_catch_up_dry_run_prints_plan(tmp_path, capsys):
    from mnemos.catch_up import run_catch_up

    vault = tmp_path
    (vault / "Mnemos").mkdir()
    (vault / "Sessions").mkdir()
    (vault / "Sessions" / "2026-04-22-a.md").write_text("x", encoding="utf-8")
    (vault / "mnemos.yaml").write_text("mine_mode: skill\n", encoding="utf-8")
    projects = tmp_path / "projects"
    projects.mkdir()
    refine_ledger = tmp_path / "refine.tsv"
    refine_ledger.touch()
    mine_ledger = tmp_path / "mine.tsv"
    mine_ledger.touch()

    result = run_catch_up(
        vault=vault, projects_dir=projects,
        refine_ledger_path=refine_ledger, mine_ledger_path=mine_ledger,
        limit=None, parallel=1, dry_run=True, yes=True,
        runner=lambda cmd: 0,
    )

    captured = capsys.readouterr().out
    assert "Plan" in captured or "plan" in captured
    assert result.processed == 0  # dry-run made no actual subprocess calls


def test_catch_up_refuses_script_mode(tmp_path):
    from mnemos.catch_up import run_catch_up, CatchUpError
    import pytest

    (tmp_path / "Mnemos").mkdir()
    (tmp_path / "mnemos.yaml").write_text("mine_mode: script\n", encoding="utf-8")

    with pytest.raises(CatchUpError, match="mine_mode: skill"):
        run_catch_up(
            vault=tmp_path,
            projects_dir=tmp_path / "p",
            refine_ledger_path=tmp_path / "r.tsv",
            mine_ledger_path=tmp_path / "m.tsv",
            dry_run=True, yes=True,
        )


def test_catch_up_dry_run_shows_counts(tmp_path, capsys):
    import json
    from mnemos.catch_up import run_catch_up

    vault = tmp_path
    (vault / "Mnemos").mkdir()
    (vault / "Sessions").mkdir()
    (vault / "Sessions" / "2026-04-22-a.md").write_text("x", encoding="utf-8")
    (vault / "Sessions" / "2026-04-22-b.md").write_text("x", encoding="utf-8")
    (vault / "mnemos.yaml").write_text("mine_mode: skill\n", encoding="utf-8")

    projects = tmp_path / "projects" / "proj"
    projects.mkdir(parents=True)
    for i in range(3):
        p = projects / f"s{i}.jsonl"
        lines = [json.dumps({"type": "user", "message": {"role": "user", "content": f"q{k}"}}) for k in range(3)]
        p.write_text("\n".join(lines), encoding="utf-8")
        import os, time
        os.utime(p, (1_000_000 + i, 1_000_000 + i))

    refine_ledger = tmp_path / "refine.tsv"
    refine_ledger.touch()
    mine_ledger = tmp_path / "mine.tsv"
    mine_ledger.touch()

    run_catch_up(
        vault=vault, projects_dir=tmp_path / "projects",
        refine_ledger_path=refine_ledger, mine_ledger_path=mine_ledger,
        limit=None, parallel=1, dry_run=True, yes=True,
        runner=lambda cmd: 0,
    )

    out = capsys.readouterr().out
    assert "Phase A (unmined Sessions):      2" in out
    assert "Phase B (unrefined JSONLs):      3" in out
