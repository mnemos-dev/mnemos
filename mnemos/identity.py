"""Identity Layer: bootstrap, refresh, rollback."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml


class IdentityError(Exception):
    """Identity layer operation failed."""


# Conservative chars-per-token estimate. Real ratio is ~3-4 for Turkish/English,
# but we treat 1 char ≈ 1 token here to err on the side of triggering the cap
# earlier rather than overshooting and OOMing the LLM context window.
_CHARS_PER_TOKEN = 1.0
_CONTEXT_CAP_TOKENS = 150_000
_CANONICAL_PROMPT_PATH = Path(__file__).parent.parent / "docs" / "prompts" / "identity-bootstrap.md"


def _count_eligible_jsonls_for_bootstrap(vault: Path) -> int:
    """Wrapper: count eligible JSONLs across all projects.

    Indirected so tests can monkey-patch a fixed count without spinning up a
    fake ~/.claude/projects tree.
    """
    from mnemos.config import load_config
    from mnemos.readiness import count_eligible_jsonls

    cfg = load_config(str(vault))
    projects = Path.home() / ".claude" / "projects"
    return count_eligible_jsonls(projects, min_user_turns=cfg.refine.min_user_turns)


def bootstrap(vault: Path, model: str = "sonnet", force: bool = False) -> Path:
    """Generate <vault>/_identity/L0-identity.md from all Sessions.

    Args:
        vault: Mnemos vault root.
        model: claude --print model (sonnet | opus).
        force: Bypass the readiness eligibility gate. Use only when the user
            explicitly opts in (e.g. ``--force``); CI / automation should
            never set this implicitly.

    Returns:
        Path to the written L0-identity.md.

    Raises:
        IdentityError: if vault has no sessions, readiness is below the
            configured threshold (and ``force`` is False), or LLM invocation
            fails.
    """
    from mnemos.config import load_config
    from mnemos.readiness import compute_readiness_pct, count_refined_sessions

    cfg = load_config(str(vault))
    threshold = cfg.identity.bootstrap_threshold_pct

    sessions_dir = vault / "Sessions"
    if not sessions_dir.exists():
        raise IdentityError(f"no sessions found in {vault} (expected {sessions_dir})")
    sessions = sorted(sessions_dir.glob("*.md"), key=lambda p: p.name, reverse=True)
    if not sessions:
        raise IdentityError(f"no sessions in {sessions_dir}")

    if not force:
        refined = count_refined_sessions(vault)
        eligible = _count_eligible_jsonls_for_bootstrap(vault)
        pct = compute_readiness_pct(refined, eligible)
        if pct < threshold:
            raise IdentityError(
                f"Identity bootstrap not yet eligible.\n"
                f"  Refined: {refined} sessions ({pct:.1f}%)\n"
                f"  Eligible JSONLs: {eligible}\n"
                f"  Threshold: {threshold}%\n"
                f"Refine more with hook (open more sessions) or run with --force to override."
            )

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


_REFRESH_PROMPT_TEMPLATE = """\
You are updating an existing Identity Layer with new Sessions.

## EXISTING PROFILE

{existing_profile}

## NEW SESSIONS (since last refresh)

{new_sessions}

## RULES

1. Yeni bilgi mevcut bir (general) preference ile çelişiyorsa, bunun proje-spesifik mi
   (yeni `(proj/<name>)` satırı) yoksa gerçek genel tercih değişikliği mi (Revize edilen
   kararlar bölümüne taşı) olduğunu açıkça belirle.
2. Yeni bilgi mevcut general'i pekiştiriyorsa dokunma.
3. Yeni bilgi yeni bir entity (kişi, araç, proje) tanıtıyorsa eklemekten çekinme.
4. Tutarlı olanlara dokunma — gereksiz revizyon yok.

3-case scenario for conflicts:
- Project-specific addition: scope farklı, no conflict, add new (proj/...) row
- Genuine general shift: old general → "Revize edilen kararlar", new general added
- Project override of general: general stays, (proj/...) override row added

## OUTPUT

Updated full profile markdown to stdout. Same frontmatter schema, updated `last_refreshed` and `session_count_at_refresh`.
"""


def refresh(vault: Path, force: bool = False, model: str = "sonnet") -> Optional[Path]:
    """Incrementally update <vault>/_identity/L0-identity.md.

    Args:
        vault: Mnemos vault root.
        force: Skip auto-trigger condition check.
        model: claude --print model.

    Returns:
        Path to updated identity file, or None if skipped (no new sessions or trigger not met).
    """
    identity_path = vault / "_identity" / "L0-identity.md"
    if not identity_path.exists():
        raise IdentityError(f"identity layer not bootstrapped at {identity_path}; run `mnemos identity bootstrap` first")

    existing = identity_path.read_text(encoding="utf-8")
    fm = _parse_frontmatter(existing)
    last_count = int(fm.get("session_count_at_refresh", 0))

    # Discover new sessions (count > last_count)
    sessions_dir = vault / "Sessions"
    all_sessions = sorted(sessions_dir.glob("*.md"), key=lambda p: p.name)
    new_sessions = all_sessions[last_count:]

    if not force:
        if len(new_sessions) < 10:
            return None  # quantity gate
        if not _has_identity_relevant_new_tags(existing, new_sessions):
            return None  # relevance gate

    # Pre-refresh backup
    _backup_identity(vault, identity_path)

    # Build prompt
    new_sessions_text = "\n\n".join(
        f"# {s.name}\n\n{s.read_text(encoding='utf-8')}" for s in new_sessions
    )
    prompt = _REFRESH_PROMPT_TEMPLATE.format(
        existing_profile=existing, new_sessions=new_sessions_text
    )

    output = _invoke_claude_print(prompt, model=model)

    # Atomic write
    tmp = identity_path.with_suffix(".tmp")
    tmp.write_text(output, encoding="utf-8")
    tmp.replace(identity_path)

    # History snapshot
    history_dir = vault / "_identity" / "_history"
    history_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M")
    snapshot = history_dir / f"{timestamp}-refresh.md"
    snapshot.write_text(output, encoding="utf-8")

    return identity_path


def _parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter from markdown. Returns {} if absent."""
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}
    try:
        return yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError:
        return {}


def _has_identity_relevant_new_tags(profile_text: str, new_sessions: list[Path]) -> bool:
    """Returns True if any new Session has a tag (proj/, person/, tool/, skill/) not present in profile."""
    profile_entities = set(re.findall(r"\[\[([^\]]+)\]\]", profile_text))
    profile_entities_lower = {e.lower() for e in profile_entities}
    for session in new_sessions:
        try:
            content = session.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = _parse_frontmatter(content)
        tags = fm.get("tags", [])
        if not isinstance(tags, list):
            continue
        for tag in tags:
            if not isinstance(tag, str):
                continue
            for prefix in ("proj/", "tool/", "person/", "skill/"):
                if tag.startswith(prefix):
                    name = tag[len(prefix):]
                    if name.lower() not in profile_entities_lower:
                        return True  # new identity-relevant entity found
    return False


def _backup_identity(vault: Path, identity_path: Path) -> None:
    """Create pre-refresh snapshot. Git-tracked vaults: auto-commit. Else: .bak file."""
    if _is_git_tracked(vault):
        try:
            subprocess.run(
                ["git", "-C", str(vault), "add", str(identity_path.relative_to(vault))],
                check=True, capture_output=True,
            )
            subprocess.run(
                [
                    "git", "-C", str(vault), "commit", "-m",
                    f"mnemos identity refresh checkpoint {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                ],
                check=False, capture_output=True,
            )
            return
        except subprocess.CalledProcessError:
            pass  # fall through to .bak
    # .bak rolling window (last 5)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M")
    bak = identity_path.parent / f"L0-identity.md.bak-{timestamp}"
    shutil.copy2(identity_path, bak)
    # Trim old .bak files
    all_baks = sorted(identity_path.parent.glob("L0-identity.md.bak-*"))
    for old in all_baks[:-5]:
        old.unlink()


def _is_git_tracked(vault: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(vault), "rev-parse", "--git-dir"],
            capture_output=True, check=False, timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def rollback(vault: Path, target: Optional[str] = None, confirm: bool = False) -> Path:
    """Restore L0-identity.md from a .bak snapshot.

    Args:
        vault: Mnemos vault root.
        target: Snapshot suffix (e.g. ``"2026-04-24-1200"``). ``None`` selects
            the latest available .bak file.
        confirm: Must be ``True`` to actually overwrite the identity file.
            Acts as a tripwire so callers (CLI / library) cannot accidentally
            destroy current state without explicit acknowledgement.

    Returns:
        Path to the restored L0-identity.md.

    Raises:
        IdentityError: if no identity file, no backups, no matching target,
            or ``confirm`` is False.
    """
    identity_dir = vault / "_identity"
    identity_path = identity_dir / "L0-identity.md"
    if not identity_path.exists():
        raise IdentityError(f"no identity file at {identity_path}")

    baks = sorted(identity_dir.glob("L0-identity.md.bak-*"))
    if not baks:
        raise IdentityError(f"no backup snapshots in {identity_dir}")

    if target is None:
        chosen = baks[-1]
    else:
        candidates = [b for b in baks if b.name.endswith(target)]
        if not candidates:
            raise IdentityError(
                f"no backup matching {target}; available: {[b.name for b in baks]}"
            )
        chosen = candidates[0]

    if not confirm:
        raise IdentityError("rollback requires confirm=True")

    shutil.copy2(chosen, identity_path)
    return identity_path


def show(vault: Path) -> str:
    """Read and return L0-identity.md content.

    Raises:
        IdentityError: if the identity file does not exist.
    """
    path = vault / "_identity" / "L0-identity.md"
    if not path.exists():
        raise IdentityError(
            f"no identity file at {path}; run `mnemos identity bootstrap` first"
        )
    return path.read_text(encoding="utf-8")
