import subprocess
import sys
from pathlib import Path


def test_cli_catch_up_help(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "mnemos.cli", "catch-up", "--help"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0
    assert "--limit" in result.stdout
    assert "--parallel" in result.stdout
    assert "--dry-run" in result.stdout


def test_cli_catch_up_dry_run_on_clean_vault(tmp_path):
    # Minimal vault with skill mine_mode + no sources → prints plan with zeros.
    (tmp_path / "Mnemos").mkdir()
    (tmp_path / "Sessions").mkdir()
    (tmp_path / "mnemos.yaml").write_text("mine_mode: skill\n", encoding="utf-8")

    import os
    env = os.environ.copy()
    env["CLAUDE_PROJECTS_DIR"] = str(tmp_path / "nonexistent-projects")

    result = subprocess.run(
        [sys.executable, "-m", "mnemos.cli", "--vault", str(tmp_path),
         "catch-up", "--dry-run", "--yes"],
        capture_output=True, text=True, env=env, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Plan" in result.stdout
