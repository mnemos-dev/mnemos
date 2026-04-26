"""Cwd-aware SessionStart auto-briefing hook wrapper.

Called by Claude Code's SessionStart hook when `recall_mode: skill`. Decides
between fast-path (inject existing briefing + bg regen) and blocking catch-up
(sync refine + brief for this cwd's unrefined JSONLs) based on a
per-cwd state file (.mnemos-cwd-state.json).

v1.0 narrative-first pivot: mining is gone. Sessions/.md are the source of
truth and the briefing skill reads them directly.

See docs/specs/2026-04-23-v0.4-task-4.3-first-ship-design.md for the full
decision tree.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any


STATE_FILENAME = ".mnemos-cwd-state.json"
CACHE_DIR = ".mnemos-briefings"
STATE_LOCK = STATE_FILENAME + ".flock"
CATCH_UP_LOCK = ".mnemos-catch-up.flock"

# Max pending JSONLs SUB-B2 will refine synchronously in one hook fire.
# Without this cap, a cwd with 300+ unprocessed JSONLs (e.g. a long-lived
# project dir) would block the session for hours. The cap limits SUB-B2 to
# the most-recent N unprocessed transcripts — enough to give a meaningful
# briefing for this session. Older unprocessed JSONLs drift down to
# auto-refine's background pipeline on subsequent sessions.
SUB_B2_PENDING_CAP = 3

# Re-entry guard: every subprocess we spawn inherits this env var, and main()
# exits silently when it sees it set. Prevents a fork-bomb cascade when
# `claude --print` subprocesses themselves fire SessionStart hooks (Claude
# Code does fire them even in print mode as of v0.4-era releases).
HOOK_ACTIVE_ENV = "MNEMOS_RECALL_HOOK_ACTIVE"


def _child_env() -> dict:
    """Env for spawned claude subprocesses: strips API key, marks re-entry."""
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    env[HOOK_ACTIVE_ENV] = "1"
    return env


def _nt_no_window_flags():
    """Windows creationflags that fully suppress a console window.

    Uses CREATE_NO_WINDOW only — it creates a hidden console process without
    any visible window. Combining with DETACHED_PROCESS is NOT safe on Windows
    (the two flags are contradictory per Microsoft docs — DETACHED_PROCESS says
    "no console at all", CREATE_NO_WINDOW says "console with hidden window").
    auto_refine uses CREATE_NO_WINDOW alone and has no fork-bomb issues; mirror
    that pattern.
    """
    import subprocess as _sp
    return getattr(_sp, "CREATE_NO_WINDOW", 0)


# ---------------------------------------------------------------------------
# Cwd slug normalization
# ---------------------------------------------------------------------------

def cwd_to_slug(cwd: str) -> str:
    """Convert a cwd path to the Claude-Code-style slug used in project dirs.

    Claude Code itself replaces every non-ASCII-word char (including Unicode
    letters like Turkish ü/German ä/Japanese 語) with '-' when naming
    ~/.claude/projects/<slug>/ folders. We must match that exactly, or
    find_unrefined_jsonls_for_cwd looks at the wrong directory and SUB-B2
    never fires for any cwd containing non-ASCII characters.

    Rules (aligned with Claude Code):
      - Strip leading/trailing whitespace and trailing path separators
      - Replace any char outside [A-Za-z0-9_-] with "-" (ASCII-only word class)
      - Collapse 3+ consecutive dashes to "--" (double-dash cap)
    """
    s = cwd.strip().rstrip("/\\")
    s = re.sub(r"[^A-Za-z0-9_-]", "-", s)
    s = re.sub(r"-{2,}", "--", s)  # cap at double-dash
    return s


# ---------------------------------------------------------------------------
# State file
# ---------------------------------------------------------------------------

@dataclass
class CwdState:
    version: int = 1
    cwds: Dict[str, Dict[str, Any]] = field(default_factory=dict)


def load_state(vault: Path) -> CwdState:
    """Load cwd-state.json; return empty state if missing or corrupt."""
    path = vault / STATE_FILENAME
    if not path.exists():
        return CwdState()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return CwdState()
    if not isinstance(raw, dict):
        return CwdState()
    return CwdState(
        version=int(raw.get("version", 1)),
        cwds=dict(raw.get("cwds", {})),
    )


def save_state(vault: Path, state: CwdState) -> None:
    """Atomic write of state JSON (write-then-rename)."""
    path = vault / STATE_FILENAME
    tmp_path = vault / (STATE_FILENAME + ".tmp")
    data = {"version": state.version, "cwds": state.cwds}
    tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, path)


# ---------------------------------------------------------------------------
# recall_mode yaml inline read
#
# Mirrors the lightweight scalar-only yaml read used elsewhere in the
# auto-refine path so we don't pull in pyyaml on the hot SessionStart path.
# ---------------------------------------------------------------------------

def read_recall_mode(vault: Path) -> str:
    """Return recall_mode from <vault>/mnemos.yaml (default: "script")."""
    yaml_path = vault / "mnemos.yaml"
    if not yaml_path.exists():
        return "script"
    try:
        text = yaml_path.read_text(encoding="utf-8")
    except OSError:
        return "script"
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("recall_mode:"):
            return s.split(":", 1)[1].strip().strip("'\"")
    return "script"


# ---------------------------------------------------------------------------
# Cache file (<vault>/.mnemos-briefings/<slug>.md)
# ---------------------------------------------------------------------------

def cache_path_for(vault: Path, cwd_slug: str) -> Path:
    return vault / CACHE_DIR / f"{cwd_slug}.md"


def read_cache_body(cache_path: Path) -> str:
    """Return cache body (frontmatter stripped). Empty string if missing/corrupt."""
    if not cache_path.exists():
        return ""
    try:
        text = cache_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    m = re.match(r"^---\r?\n.*?\r?\n---\r?\n", text, re.DOTALL)
    if m:
        return text[m.end():].lstrip("\n")
    return text


def write_cache(
    cache_path: Path,
    body: str,
    cwd: str,
    session_count: int,
    drawer_count: int,
    generated_at: str | None = None,
) -> None:
    """Write cache file with frontmatter + body. Creates parent dir if needed."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if generated_at is None:
        from datetime import datetime
        generated_at = datetime.now().isoformat(timespec="seconds")
    front = (
        f"---\n"
        f"cwd: {cwd}\n"
        f"generated_at: {generated_at}\n"
        f"session_count_used: {session_count}\n"
        f"drawer_count_used: {drawer_count}\n"
        f"---\n\n"
    )
    cache_path.write_text(front + body.lstrip("\n"), encoding="utf-8")


# ---------------------------------------------------------------------------
# Session frontmatter counter for staleness check
# ---------------------------------------------------------------------------

def count_refined_sessions_for_cwd(vault: Path, cwd: str) -> int:
    """Count Sessions/*.md files whose frontmatter cwd matches exactly.

    Case-sensitive, trailing whitespace/slash on both sides trimmed before
    compare. Sessions without cwd frontmatter are excluded.
    """
    target = cwd.strip().rstrip("/\\")
    sessions_dir = vault / "Sessions"
    if not sessions_dir.exists():
        return 0
    count = 0
    for md in sessions_dir.glob("*.md"):
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
        if not m:
            continue
        front = m.group(1)
        for line in front.splitlines():
            s = line.strip()
            if s.startswith("cwd:"):
                val = s.split(":", 1)[1].strip().strip("'\"")
                if val.rstrip("/\\") == target:
                    count += 1
                break
    return count


# ---------------------------------------------------------------------------
# Refine ledger + unrefined JSONL discovery
# ---------------------------------------------------------------------------

DEFAULT_REFINE_LEDGER = Path.home() / ".claude/skills/mnemos-refine-transcripts/state/processed.tsv"
DEFAULT_CLAUDE_PROJECTS = Path.home() / ".claude/projects"


def load_refine_ledger_jsonls(ledger: Path) -> set[str]:
    """Return set of JSONL abs paths the refine skill has already processed.

    Ledger format: <jsonl>\\t<status>\\t<session_md_or_reason> (3 cols,
    tab-separated). Status is OK (refine succeeded → session_md written)
    or SKIP (skill decided transcript is noise / too-short).

    Both OK and SKIP count as "processed" for pending-discovery purposes.
    Without SKIP inclusion, a noise JSONL (1-turn debug session, bash
    escape collision, etc.) keeps reappearing as pending on every hook
    fire: SUB-B2 sync-refines → skill returns SKIP → ledger grows, JSONL
    stays pending → repeat on next session start. The user pays minutes
    of sync-refine latency every single time for zero briefing value.
    """
    out: set[str] = set()
    if not ledger.exists():
        return out
    try:
        with ledger.open("r", encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                parts = raw.rstrip("\r\n").split("\t")
                if len(parts) < 3:
                    continue
                if parts[1] in ("OK", "SKIP"):
                    out.add(parts[0])
    except OSError:
        pass
    return out


def find_unrefined_jsonls_for_cwd(
    cwd_slug: str,
    projects_root: Path,
    ledger: Path,
) -> list[Path]:
    """List .jsonl files in ~/.claude/projects/<slug>/ NOT in refine ledger.

    Sorted by mtime (oldest first). JSONLs with fewer than MIN_USER_TURNS
    real user turns are filtered out — they're fork-bomb byproducts,
    '/clear' resume sessions, or aborted sessions that the briefing skill
    would just SKIP anyway. Matches auto_refine's picker behavior (v0.3.11
    min-user-turns filter). Without this, SUB-B2 could sync-refine 3
    fork-bomb JSONLs for every session start, wasting minutes.

    The caller should also skip any JSONL whose PID marker indicates a
    live session (handled in handle_session_start via transcript_path).
    """
    # Local import to avoid shuffling module-level import ordering
    from mnemos.auto_refine import _count_user_turns, MIN_USER_TURNS

    proj_dir = projects_root / cwd_slug
    if not proj_dir.exists():
        return []
    processed = load_refine_ledger_jsonls(ledger)
    candidates: list[Path] = []
    for jsonl in proj_dir.glob("*.jsonl"):
        if str(jsonl) in processed:
            continue
        if _count_user_turns(jsonl) < MIN_USER_TURNS:
            continue
        candidates.append(jsonl)
    return sorted(candidates, key=lambda p: p.stat().st_mtime)


# ---------------------------------------------------------------------------
# Statusline status file (shared with auto_refine.STATUS_FILENAME)
# ---------------------------------------------------------------------------

STATUS_FILENAME = ".mnemos-hook-status.json"


def read_status(vault: Path) -> Dict[str, Any]:
    p = vault / STATUS_FILENAME
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_status(
    vault: Path,
    phase: str,
    current: int | None = None,
    total: int | None = None,
    cwd_slug: str | None = None,
    sub_phase: str | None = None,
    last_outcome: str | None = None,
) -> None:
    """Merge given fields into .mnemos-hook-status.json.

    Preserves fields written by other hooks (e.g. auto_refine's last_ok,
    last_skip, backlog) — only overwrites the keys we pass.
    """
    data = read_status(vault)
    data["phase"] = phase
    if current is not None:
        data["current"] = current
    if total is not None:
        data["total"] = total
    if cwd_slug is not None:
        data["cwd_slug"] = cwd_slug
    if sub_phase is not None:
        data["sub_phase"] = sub_phase
    elif phase != "idle":
        data.setdefault("sub_phase", "catch-up")
    if last_outcome is not None:
        data["last_outcome"] = last_outcome

    path = vault / STATUS_FILENAME
    tmp_path = vault / (STATUS_FILENAME + ".tmp")
    tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, path)


# ---------------------------------------------------------------------------
# Subprocess runners for skill invocations
# ---------------------------------------------------------------------------

import tempfile


@dataclass
class RefineResult:
    ok: bool
    jsonl: Path


@dataclass
class BriefResult:
    ok: bool
    body: str


def _default_runner(cmd) -> int:
    """Invoke claude subprocess; strip ANTHROPIC_API_KEY so subscription is used.
    Marks re-entry via HOOK_ACTIVE_ENV so recursive SessionStart fires exit silently."""
    import subprocess
    kwargs: dict = {"env": _child_env()}
    if os.name == "nt":
        kwargs["creationflags"] = _nt_no_window_flags()
    try:
        return subprocess.call(list(cmd), **kwargs)
    except (FileNotFoundError, OSError):
        return 1


def _default_runner_stdout(cmd, stdout_path=None) -> int:
    """Like _default_runner but redirects stdout to the given file path."""
    import subprocess
    kwargs: dict = {"env": _child_env()}
    if os.name == "nt":
        kwargs["creationflags"] = _nt_no_window_flags()
    try:
        if stdout_path is not None:
            with open(stdout_path, "w", encoding="utf-8") as fh:
                return subprocess.call(list(cmd), stdout=fh, **kwargs)
        return subprocess.call(list(cmd), **kwargs)
    except (FileNotFoundError, OSError):
        return 1


def _build_skill_cmd(skill: str, arg: str) -> list[str]:
    """Build: claude --print --dangerously-skip-permissions --model sonnet "/<skill> <arg>" """
    return [
        "claude",
        "--print",
        "--dangerously-skip-permissions",
        "--model", "sonnet",
        f"/{skill} {arg}",
    ]


def run_refine_sync(jsonl: Path, runner=None) -> RefineResult:
    runner = runner or _default_runner
    cmd = _build_skill_cmd("mnemos-refine-transcripts", str(jsonl))
    rc = runner(cmd)
    return RefineResult(ok=(rc == 0), jsonl=jsonl)


def run_brief_sync(cwd: str, runner=None) -> BriefResult:
    runner = runner or _default_runner_stdout
    cmd = _build_skill_cmd("mnemos-briefing", cwd)
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    tmp_path = tmp.name
    tmp.close()
    try:
        rc = runner(cmd, stdout_path=tmp_path)
        if rc != 0:
            return BriefResult(ok=False, body="")
        body = Path(tmp_path).read_text(encoding="utf-8")
        return BriefResult(ok=True, body=body)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Main decision tree — handle_session_start
# ---------------------------------------------------------------------------

import time
import subprocess as _subprocess

VALID_SESSION_SOURCES = {"", "startup", "resume", "clear"}


@dataclass
class SessionStartInput:
    cwd: str
    source: str  # "startup" | "resume" | "clear" | "compact" | ""
    transcript_path: str


@dataclass
class HandleOutcome:
    outcome: str
    injected_context: str = ""


def brief_and_cache(cwd: str, vault: Path, brief_runner=None) -> bool:
    """Run the briefing skill for `cwd` and persist the result to cache.

    This is the cache-producing side of the hook. Called directly in two
    places:
      1. `_spawn_bg_brief` → detached subprocess invokes us via the
         `--brief-and-cache` main() entry, so SUB-B1's bg regeneration
         actually writes a cache file (the old DEVNULL-pipe pattern
         discarded the body and never created a cache).
      2. Manual / future foreground callers that want to warm the cache.

    Returns True on success (cache file written), False otherwise.
    On failure the cache file is NOT written — a fresh-but-empty cache
    would otherwise mask real briefings forever after.
    """
    result = run_brief_sync(cwd, runner=brief_runner)
    if not result.ok or not result.body.strip():
        return False
    cache_p = cache_path_for(vault, cwd_to_slug(cwd))
    session_n = count_refined_sessions_for_cwd(vault, cwd)
    write_cache(
        cache_p,
        body=result.body,
        cwd=cwd,
        session_count=session_n,
        drawer_count=0,
    )
    return True


def catchup_and_cache(
    cwd: str,
    vault: Path,
    projects_root: Path | None = None,
    ledger: Path | None = None,
    subprocess_runner=None,
    brief_runner=None,
) -> bool:
    """Refine pending JSONLs for this cwd, then brief+cache.

    Called from the --catchup subcommand (detached bg subprocess). Extends
    brief_and_cache with a pending refine prelude, so the next session
    opens with fresh content. If no pending JSONLs exist, this is equivalent
    to brief_and_cache (just refreshes cache body).

    v1.0 narrative-first pivot: no mining step. Sessions/.md are the source
    of truth and the briefing skill reads them directly.

    Limits work to SUB_B2_PENDING_CAP most-recent pending JSONLs — older
    ones drift to auto_refine's async cadence. Refine failures don't block
    the brief step: previous sessions' content is already in the vault.

    Returns True if brief+cache step succeeded.
    """
    if projects_root is None:
        projects_root = DEFAULT_CLAUDE_PROJECTS
    if ledger is None:
        ledger = DEFAULT_REFINE_LEDGER

    slug = cwd_to_slug(cwd)
    pending = find_unrefined_jsonls_for_cwd(
        cwd_slug=slug, projects_root=projects_root, ledger=ledger,
    )
    if len(pending) > SUB_B2_PENDING_CAP:
        pending = pending[-SUB_B2_PENDING_CAP:]

    for jsonl in pending:
        run_refine_sync(jsonl, runner=subprocess_runner)
        # Refine failures are non-fatal: previous sessions' content is
        # already in the vault, briefing will just skip this JSONL.

    return brief_and_cache(cwd, vault, brief_runner=brief_runner)


def _spawn_bg_catchup(cwd: str, vault: Path) -> None:
    """Spawn a detached bg process that runs `catchup_and_cache(cwd, vault)`.

    Non-blocking. Errors are swallowed (diagnostic-only). The child re-enters
    this module through its `--catchup` subcommand, refines pending
    JSONLs, and rewrites the cache at <vault>/.mnemos-briefings/<slug>.md.

    Uses CREATE_NO_WINDOW on Windows (same pattern as auto_refine) so no
    console window flashes. Child inherits HOOK_ACTIVE_ENV so any nested
    SessionStart fires exit silently via the re-entry guard in main().
    """
    try:
        cmd = [
            sys.executable, "-m", "mnemos.recall_briefing",
            "--catchup",
            "--cwd", cwd,
            "--vault", str(vault),
        ]
        kwargs: dict = {
            "stdout": _subprocess.DEVNULL,
            "stderr": _subprocess.DEVNULL,
            "stdin": _subprocess.DEVNULL,
            "env": _child_env(),
        }
        if os.name == "nt":
            kwargs["creationflags"] = _nt_no_window_flags()
        _subprocess.Popen(cmd, **kwargs)
    except (OSError, FileNotFoundError):
        pass


# Backward-compat alias: legacy _spawn_bg_brief callers (tests, external code)
# now go through the same --catchup path. When pending is empty,
# catchup_and_cache is effectively brief-only, so semantics match.
_spawn_bg_brief = _spawn_bg_catchup


def handle_session_start(
    inp: SessionStartInput,
    vault: Path,
    projects_root: Path,
    ledger: Path,
    subprocess_runner=None,  # retained for backward-compat; unused in async path
    brief_runner=None,        # same
    bg_spawn=None,
) -> HandleOutcome:
    """Main decision tree. Returns in <1s on every branch; all subprocess
    work is delegated to a detached bg catchup spawn.

    Pending JSONLs present → always fire bg catchup (refine+brief)
    and refresh cache for the next session. Cache presence only decides
    whether to inject something NOW on this session:
      - pending=0, cache present → inject (bg refreshes anyway)
      - pending=0, cache missing → silent (bg creates cache)
      - pending>0, cache present → inject stale cache + bg catchup
      - pending>0, cache missing → silent + bg catchup

    injected_context (if non-empty) is what the wrapper should emit as
    additionalContext JSON to Claude Code's stdout.
    """
    bg_spawn = bg_spawn or _spawn_bg_catchup

    # Filter: bad source → exit
    if inp.source not in VALID_SESSION_SOURCES:
        return HandleOutcome(outcome="skipped_source")

    # Subagent dispatches
    if "/subagents/" in (inp.transcript_path or ""):
        return HandleOutcome(outcome="skipped_subagent")

    # Mode gate
    if read_recall_mode(vault) != "skill":
        return HandleOutcome(outcome="skipped_mode")

    # Load state
    state = load_state(vault)
    slug = cwd_to_slug(inp.cwd)
    now = time.time()

    cwd_info = state.cwds.get(slug)

    # CASE A — first visit ever
    if cwd_info is None:
        state.cwds[slug] = {
            "cwd": inp.cwd,
            "first_seen": now,
            "last_seen": now,
            "visit_count": 1,
            "last_session_id": None,
        }
        save_state(vault, state)
        return HandleOutcome(outcome="first_visit")

    # CASE B — return visit
    cwd_info["last_seen"] = now
    cwd_info["visit_count"] = cwd_info.get("visit_count", 1) + 1

    # Check for unrefined JSONLs in this cwd (live session excluded)
    pending = find_unrefined_jsonls_for_cwd(
        cwd_slug=slug,
        projects_root=projects_root,
        ledger=ledger,
    )
    live = Path(inp.transcript_path) if inp.transcript_path else None
    if live is not None:
        pending = [p for p in pending if p != live]

    cache_p = cache_path_for(vault, slug)
    cache_exists = cache_p.exists()

    # Always fire bg catchup — it's a no-op refine loop when pending is empty,
    # just refreshes the cache body. Hook path stays <1s either way.
    bg_spawn(inp.cwd, vault)
    save_state(vault, state)

    if cache_exists:
        body = read_cache_body(cache_p)
        if pending:
            return HandleOutcome(outcome="fast_path_injected_with_catchup", injected_context=body)
        return HandleOutcome(outcome="fast_path_injected", injected_context=body)

    # No cache — silent this session; next session opens with fresh cache
    # produced by the bg catchup we just fired.
    if pending:
        return HandleOutcome(outcome="bg_catching_up")
    return HandleOutcome(outcome="fast_path_no_cache")


# ---------------------------------------------------------------------------
# Main entry — called by Claude Code SessionStart hook
# ---------------------------------------------------------------------------

import sys


# ---------------------------------------------------------------------------
# v1.0 stale-hook detection — see auto_refine_hook.py for design notes.
# Mirrors the auto-refine shim so a stale ``mnemos-recall-briefing`` entry
# (v0.x ``_version`` or missing ``_version``) never crashes SessionStart.
# ---------------------------------------------------------------------------


def _user_settings_path() -> Path:
    return Path.home() / ".claude" / "settings.json"


def _detect_stale_hook_signature(managed_by: str) -> bool:
    """Return True iff a SessionStart entry with ``_managed_by == managed_by``
    exists but its ``_version`` is anything other than ``"v1.0"``.
    """
    settings_path = _user_settings_path()
    if not settings_path.exists():
        return False
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    for entry in data.get("hooks", {}).get("SessionStart", []):
        if entry.get("_managed_by") == managed_by:
            return entry.get("_version") != "v1.0"
    return False


def _resolve_vault(explicit: str | None = None) -> Path | None:
    """Resolve vault from explicit arg, env, or cwd upward walk. Return None if unresolvable."""
    if explicit:
        p = Path(explicit)
        if p.exists():
            return p
    v = os.environ.get("MNEMOS_VAULT")
    if v:
        p = Path(v)
        if p.exists():
            return p
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if (parent / "mnemos.yaml").exists():
            return parent
    return None


@dataclass
class _ParsedArgs:
    vault: str | None
    brief_and_cache: bool
    catchup: bool
    cwd: str | None


def _parse_args(argv: list[str] | None) -> _ParsedArgs:
    """Parse CLI flags. Three modes:
      - hook mode (default): consume stdin JSON, dispatch handle_session_start
      - --brief-and-cache: brief-only cache regen (retained for backward-compat)
      - --catchup: pending refine+brief pipeline (default bg entry)
    """
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--vault", default=None)
    parser.add_argument("--brief-and-cache", action="store_true")
    parser.add_argument("--catchup", action="store_true")
    parser.add_argument("--cwd", default=None)
    try:
        ns, _ = parser.parse_known_args(argv)
    except SystemExit:
        return _ParsedArgs(vault=None, brief_and_cache=False, catchup=False, cwd=None)
    return _ParsedArgs(
        vault=ns.vault,
        brief_and_cache=ns.brief_and_cache,
        catchup=ns.catchup,
        cwd=ns.cwd,
    )


def main(argv: list[str] | None = None) -> int:
    """Parse hook stdin JSON, run decision tree, emit additionalContext JSON on stdout.

    Two modes:
      1. Hook mode (default): consume SessionStart JSON on stdin, run
         handle_session_start, emit additionalContext on stdout.
      2. `--brief-and-cache --cwd X --vault Y`: run brief_and_cache(X, Y)
         and exit. Used by _spawn_bg_brief to produce the briefing cache
         in a detached background process.
    """
    # Re-entry guard: if our own subprocess spawned a `claude --print` which
    # fired SessionStart and re-invoked us, HOOK_ACTIVE_ENV is set. Exit
    # immediately to break the recursion BEFORE any state / subprocess work.
    if os.environ.get(HOOK_ACTIVE_ENV):
        return 0

    # v1.0 stale-hook guard: if our own settings.json entry is still v0.x,
    # the user upgraded the package without re-running ``mnemos install-hook
    # --v1``. Print guidance to stderr and exit 0 so SessionStart finishes
    # cleanly (no crash dialog, no stuck terminal).
    if _detect_stale_hook_signature("mnemos-recall-briefing"):
        print(
            "Mnemos v1.0 detected an outdated SessionStart hook entry.\n"
            "Run `mnemos install-hook --v1` to update.\n"
            "Skipping this run to avoid errors.",
            file=sys.stderr,
        )
        return 0

    if argv is None:
        argv = sys.argv[1:]
    parsed = _parse_args(argv)

    # --catchup subcommand — foreground refine+brief pipeline. Default
    # bg entry from _spawn_bg_catchup. Does NOT touch stdin or hook state.
    if parsed.catchup:
        if not parsed.cwd or not parsed.vault:
            return 0
        vault = Path(parsed.vault)
        if not vault.exists():
            return 0
        try:
            catchup_and_cache(parsed.cwd, vault)
        except Exception:
            return 0
        return 0

    # --brief-and-cache subcommand — brief-only regen (backward-compat).
    # Kept for external callers and legacy test imports.
    if parsed.brief_and_cache:
        if not parsed.cwd or not parsed.vault:
            return 0
        vault = Path(parsed.vault)
        if not vault.exists():
            return 0
        try:
            brief_and_cache(parsed.cwd, vault)
        except Exception:
            return 0
        return 0

    # Hook mode. Windows Python opens stdin/stdout in cp1252 by default;
    # Claude Code sends UTF-8 JSON on stdin, and the briefing body we emit
    # on stdout often contains Turkish/non-ASCII chars that cp1252 CANNOT
    # represent (ş/ğ, 日本語, etc). Without these reconfigures:
    #   - stdin: 'ü' (UTF-8 C3 BC) surfaces as mojibake 'Ã¼'
    #   - stdout: print(json.dumps(body)) raises UnicodeEncodeError → hook
    #     exits 1 → Claude Code silently drops additionalContext (user gets
    #     no briefing despite successful SUB-B2 catch-up).
    # Guarded by broad except because test doubles (StringIO) and some
    # shells provide streams that don't implement reconfigure().
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError):
        pass
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError):
        pass

    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return 0

    inp = SessionStartInput(
        cwd=data.get("cwd", ""),
        source=data.get("source", ""),
        transcript_path=data.get("transcript_path", ""),
    )

    vault = _resolve_vault(parsed.vault)
    if vault is None:
        return 0

    try:
        result = handle_session_start(
            inp,
            vault=vault,
            projects_root=DEFAULT_CLAUDE_PROJECTS,
            ledger=DEFAULT_REFINE_LEDGER,
        )
    except Exception:
        # Never let the hook crash Claude Code
        return 0

    if result.injected_context:
        out = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": result.injected_context,
            }
        }
        print(json.dumps(out, ensure_ascii=False))

    return 0


# ---------------------------------------------------------------------------
# install-recall-hook — settings.json management
# ---------------------------------------------------------------------------

RECALL_HOOK_TIMEOUT_MS = 600_000  # 10 minutes for catch-up worst case
RECALL_HOOK_MARKER = "mnemos-recall-briefing"
SETTINGS_PATH = Path.home() / ".claude" / "settings.json"


@dataclass
class HookInstallResult:
    status: str  # "installed" | "already-installed" | "uninstalled" | "not-present"
    settings_path: Path


def _load_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_settings(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _recall_entry(vault: Path) -> dict:
    """Build a Claude Code SessionStart hook group entry.

    Claude Code expects each SessionStart list item to be a {matcher, hooks}
    object with a nested hooks list. We stamp `_managed_by` for idempotent
    detection on reinstall/uninstall.
    """
    # Forward-slash vault path on Windows survives Claude Code's hook
    # dispatcher (which eats \P, \m, \s, \a escapes); mirrors auto_refine.
    if os.name == "nt":
        vault_arg = str(vault).replace("\\", "/")
        full_cmd = f"python -m mnemos.recall_briefing --vault {vault_arg}"
    else:
        full_cmd = f'python -m mnemos.recall_briefing --vault "{vault}"'
    return {
        "matcher": "",
        "_managed_by": RECALL_HOOK_MARKER,
        "hooks": [{
            "type": "command",
            "command": full_cmd,
            "timeout": RECALL_HOOK_TIMEOUT_MS,
        }],
    }


def _is_recall_entry(entry: dict) -> bool:
    """Detect the recall-briefing hook group by marker or legacy command sniff."""
    if entry.get("_managed_by") == RECALL_HOOK_MARKER:
        return True
    # Legacy flat layout (pre-nested-schema) or custom manual edits
    if "recall_briefing" in (entry.get("command") or ""):
        return True
    for h in entry.get("hooks", []) or []:
        if "recall_briefing" in (h.get("command") or ""):
            return True
    return False


def install_recall_hook(vault: Path, uninstall: bool = False) -> HookInstallResult:
    """Add/remove the recall-briefing SessionStart hook entry in settings.json.

    Hook group schema (matches Claude Code + auto_refine convention):
        {"matcher": "", "_managed_by": RECALL_HOOK_MARKER,
         "hooks": [{"type": "command", "command": ..., "timeout": ...}]}
    """
    data = _load_settings(SETTINGS_PATH)
    data.setdefault("hooks", {})
    data["hooks"].setdefault("SessionStart", [])

    entries = data["hooks"]["SessionStart"]

    if uninstall:
        before = len(entries)
        data["hooks"]["SessionStart"] = [e for e in entries if not _is_recall_entry(e)]
        _save_settings(SETTINGS_PATH, data)
        status = "uninstalled" if before != len(data["hooks"]["SessionStart"]) else "not-present"
        return HookInstallResult(status=status, settings_path=SETTINGS_PATH)

    # Install
    if any(_is_recall_entry(e) for e in entries):
        return HookInstallResult(status="already-installed", settings_path=SETTINGS_PATH)

    entries.append(_recall_entry(vault))
    _save_settings(SETTINGS_PATH, data)
    return HookInstallResult(status="installed", settings_path=SETTINGS_PATH)


if __name__ == "__main__":
    sys.exit(main())
