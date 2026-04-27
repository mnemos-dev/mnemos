"""Tests for `mnemos identity ...` CLI."""
import subprocess
from pathlib import Path


def test_cli_identity_subcommand_registered():
    """`mnemos identity --help` returns 0."""
    result = subprocess.run(
        ["python", "-m", "mnemos.cli", "identity", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "bootstrap" in result.stdout
    assert "refresh" in result.stdout
    assert "rollback" in result.stdout
    assert "show" in result.stdout


def test_cli_identity_show_emits_content(tmp_path):
    vault = tmp_path / "vault"
    (vault / "_identity").mkdir(parents=True)
    (vault / "_identity" / "L0-identity.md").write_text(
        "# Test Identity Profile\n", encoding="utf-8"
    )
    # Write minimal mnemos.yaml so cli loads
    (vault / "mnemos.yaml").write_text(f"vault: {vault}\nlanguages: [en]\n", encoding="utf-8")

    result = subprocess.run(
        ["python", "-m", "mnemos.cli", "identity", "show", "--vault", str(vault)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "Test Identity Profile" in result.stdout


def test_cli_identity_bootstrap_accepts_force_flag():
    """`mnemos identity bootstrap --help` advertises a --force flag."""
    result = subprocess.run(
        ["python", "-m", "mnemos.cli", "identity", "bootstrap", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "--force" in result.stdout
