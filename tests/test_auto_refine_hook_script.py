"""Small tests for scripts/auto_refine_hook.py CLI arg handling."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_hook_script_accepts_vault_cli_arg(tmp_path, monkeypatch):
    """Script must prefer --vault CLI arg over MNEMOS_VAULT env."""
    import os

    script = REPO_ROOT / "scripts" / "auto_refine_hook.py"
    # Pass the full environment minus MNEMOS_VAULT so mnemos is importable
    # (dev install via pip install -e) while the env var path is absent.
    env = {k: v for k, v in os.environ.items() if k != "MNEMOS_VAULT"}
    # No MNEMOS_VAULT in env, pass via --vault arg; script should exit 0 cleanly
    result = subprocess.run(
        [sys.executable, str(script), "--vault", str(tmp_path)],
        input="",
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )
    # Exit 0 (no crash). Status file should have been written.
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert (tmp_path / ".mnemos-hook-status.json").exists()
