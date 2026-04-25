"""Tests for `mnemos reindex` CLI."""
import subprocess


def test_cli_reindex_subcommand_registered():
    """`mnemos reindex --help` returns 0 and lists --backend."""
    result = subprocess.run(
        ["python", "-m", "mnemos.cli", "reindex", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "--backend" in result.stdout
    assert "--no-backup" in result.stdout
