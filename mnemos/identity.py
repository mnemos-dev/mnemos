"""Identity Layer: bootstrap, refresh, rollback."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class IdentityError(Exception):
    """Identity layer operation failed."""


# Conservative chars-per-token estimate. Real ratio is ~3-4 for Turkish/English,
# but we treat 1 char ≈ 1 token here to err on the side of triggering the cap
# earlier rather than overshooting and OOMing the LLM context window.
_CHARS_PER_TOKEN = 1.0
_CONTEXT_CAP_TOKENS = 150_000
_CANONICAL_PROMPT_PATH = Path(__file__).parent.parent / "docs" / "prompts" / "identity-bootstrap.md"


def bootstrap(vault: Path, model: str = "sonnet") -> Path:
    """Generate <vault>/_identity/L0-identity.md from all Sessions.

    Args:
        vault: Mnemos vault root.
        model: claude --print model (sonnet | opus).

    Returns:
        Path to the written L0-identity.md.

    Raises:
        IdentityError: if vault has no sessions or LLM invocation fails.
    """
    sessions_dir = vault / "Sessions"
    if not sessions_dir.exists():
        raise IdentityError(f"no sessions found in {vault} (expected {sessions_dir})")
    sessions = sorted(sessions_dir.glob("*.md"), key=lambda p: p.name, reverse=True)
    if not sessions:
        raise IdentityError(f"no sessions in {sessions_dir}")

    # Apply context cap
    selected = _select_sessions_with_cap(sessions)

    # Build LLM input
    canonical_prompt = _CANONICAL_PROMPT_PATH.read_text(encoding="utf-8")
    sessions_text = "\n\n".join(
        f"# {s.name}\n\n{s.read_text(encoding='utf-8')}" for s in selected
    )
    full_input = f"{canonical_prompt}\n\n---\n\n## Sessions\n\n{sessions_text}"

    # Invoke
    output = _invoke_claude_print(full_input, model=model)

    # Write output
    identity_dir = vault / "_identity"
    identity_dir.mkdir(exist_ok=True)
    history_dir = identity_dir / "_history"
    history_dir.mkdir(exist_ok=True)

    identity_path = identity_dir / "L0-identity.md"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M")
    snapshot_path = history_dir / f"{timestamp}-bootstrap.md"

    # Atomic write of identity
    tmp = identity_path.with_suffix(".tmp")
    tmp.write_text(output, encoding="utf-8")
    tmp.replace(identity_path)

    # History snapshot
    snapshot_path.write_text(output, encoding="utf-8")

    return identity_path


def _select_sessions_with_cap(sessions: list[Path]) -> list[Path]:
    """Apply 150K context cap with hybrid (latest 100 + baseline) sampling."""
    total_chars = sum(s.stat().st_size for s in sessions)
    total_tokens = total_chars / _CHARS_PER_TOKEN
    if total_tokens <= _CONTEXT_CAP_TOKENS:
        return sessions
    # Hybrid: latest 100 + baseline (first 5 + every 10th)
    latest_100 = sessions[:100]
    earlier = sessions[100:]
    baseline = earlier[:5] + earlier[5::10]
    # Dedup, preserve recency order
    selected = latest_100 + [s for s in baseline if s not in latest_100]
    return selected


def _invoke_claude_print(prompt_input: str, model: str = "sonnet") -> str:
    """Invoke `claude --print` with the given input. Returns stdout text."""
    cmd = [
        "claude",
        "--print",
        "--dangerously-skip-permissions",
        "--model",
        model,
    ]
    proc = subprocess.run(
        cmd,
        input=prompt_input,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=600,  # 10 min cap
    )
    if proc.returncode != 0:
        raise IdentityError(f"claude --print failed (exit {proc.returncode}): {proc.stderr[:500]}")
    return proc.stdout
