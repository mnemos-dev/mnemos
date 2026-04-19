"""Tests for `mnemos mine --pilot-llm` CLI wiring.

Deep mechanics live in test_pilot.py; this module only verifies the CLI glue:
plan summary print, --yes short-circuit, run_pilot + write_pilot_report
delegation, hand-off text.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from mnemos import cli as cli_mod
from mnemos.pilot import (
    PilotError,
    PilotPlan,
    PilotResult,
    SessionOutcome,
    TokenUsage,
)


def _write_vault(tmp_path: Path) -> Path:
    (tmp_path / "mnemos.yaml").write_text(
        "vault_path: " + str(tmp_path).replace("\\", "/") + "\n"
        "languages: [en]\n"
        "use_llm: false\n"
        "halls: [decisions, events, problems, preferences, emotional]\n"
        "watcher_ignore: []\n",
        encoding="utf-8",
    )
    sdir = tmp_path / "Sessions"
    sdir.mkdir()
    s = sdir / "2026-04-19-test.md"
    s.write_text("---\ndate: 2026-04-19\nproject: Mnemos\n---\n\n# test\n", encoding="utf-8")
    import os
    os.utime(s, (time.time() - 10, time.time() - 10))
    return tmp_path


def _mine_args(vault: Path, *, yes: bool = True, limit: int = 10) -> argparse.Namespace:
    return argparse.Namespace(
        vault=str(vault),
        path=None,
        llm=False,
        rebuild=False,
        dry_run=False,
        yes=yes,
        no_backup=False,
        pilot_llm=True,
        pilot_limit=limit,
    )


def test_pilot_cli_prints_plan_and_hands_off(tmp_path, capsys):
    vault = _write_vault(tmp_path)

    fake_result = PilotResult(
        plan=PilotPlan(
            vault=vault,
            sessions=[vault / "Sessions" / "2026-04-19-test.md"],
            script_palace=vault / "Mnemos",
            skill_palace=vault / "Mnemos-pilot",
            limit=10,
        ),
        outcomes=[
            SessionOutcome(
                session=vault / "Sessions" / "2026-04-19-test.md",
                exit_code=0,
                drawer_count=4,
                outcome="ok",
                reason="",
                usage=TokenUsage(input_tokens=2500, output_tokens=600),
            )
        ],
        skill_total_tokens=TokenUsage(input_tokens=2500, output_tokens=600),
        skill_elapsed_sec=22.3,
    )

    with patch("mnemos.pilot.run_pilot", return_value=fake_result), \
         patch("mnemos.pilot.write_pilot_report", return_value=tmp_path / "docs" / "pilots" / "report.md"):
        cli_mod.cmd_mine(_mine_args(vault))

    out = capsys.readouterr().out
    assert "Pilot plan:" in out
    assert "Sessions:       1" in out
    assert str(vault / "Mnemos-pilot") in out
    assert "Pilot complete: OK=1" in out
    assert "drawers=4" in out
    assert "Tokens consumed: 3,100" in out
    assert "mnemos pilot --accept script" in out
    assert "mnemos pilot --accept skill" in out


def test_pilot_cli_exits_cleanly_when_user_declines(tmp_path, capsys, monkeypatch):
    vault = _write_vault(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: "n")

    args = _mine_args(vault, yes=False)

    with patch("mnemos.pilot.run_pilot") as run_mock:
        cli_mod.cmd_mine(args)

    assert run_mock.call_count == 0
    out = capsys.readouterr().out
    assert "Aborted." in out


def test_pilot_cli_reports_pilot_error_and_exits(tmp_path, capsys):
    """build_plan raises PilotError (e.g. no Sessions/) → CLI prints to stderr and exits 2."""
    (tmp_path / "mnemos.yaml").write_text(
        "vault_path: " + str(tmp_path).replace("\\", "/") + "\n"
        "languages: [en]\nuse_llm: false\nhalls: []\nwatcher_ignore: []\n",
        encoding="utf-8",
    )
    args = _mine_args(tmp_path)

    with pytest.raises(SystemExit) as exc:
        cli_mod.cmd_mine(args)

    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "Pilot error" in err
    assert "No refined sessions" in err


# ---------------------------------------------------------------------------
# mnemos pilot --accept {script, skill}
# ---------------------------------------------------------------------------


def _pilot_accept_args(vault: Path, mode: str) -> argparse.Namespace:
    return argparse.Namespace(vault=str(vault), accept=mode)


def _make_pilot_palace(vault: Path, name: str = "Mnemos-pilot") -> None:
    d = vault / name / "wings" / "Mnemos" / "r" / "decisions"
    d.mkdir(parents=True)
    (d / "x.md").write_text("marker", encoding="utf-8")


def test_cmd_pilot_accept_script_prints_summary(tmp_path, capsys):
    vault = _write_vault(tmp_path)
    _make_pilot_palace(vault)

    cli_mod.cmd_pilot(_pilot_accept_args(vault, "script"))

    out = capsys.readouterr().out
    assert "Accepted mode: script" in out
    assert "Recycled:" in out
    assert not (vault / "Mnemos-pilot").exists()


def test_cmd_pilot_accept_skill_prints_warning(tmp_path, capsys):
    vault = _write_vault(tmp_path)
    _make_pilot_palace(vault)

    cli_mod.cmd_pilot(_pilot_accept_args(vault, "skill"))

    out = capsys.readouterr().out
    assert "Accepted mode: skill" in out
    assert "Promoted:" in out
    assert "mine_mode = skill" in out
    assert "WARNING" in out
    assert (vault / "Mnemos").exists()


def test_cmd_pilot_accept_skill_errors_without_pilot_palace(tmp_path, capsys):
    vault = _write_vault(tmp_path)
    # No Mnemos-pilot/ created

    with pytest.raises(SystemExit) as exc:
        cli_mod.cmd_pilot(_pilot_accept_args(vault, "skill"))

    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "Skill palace not found" in err
